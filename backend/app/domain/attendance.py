from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
import re


class AttendanceStatus(StrEnum):
    OPEN = "OPEN"
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    HALF_DAY = "HALF_DAY"
    LEAVE = "LEAVE"
    LATE = "LATE"


class CorrectionStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AttendanceError(ValueError):
    pass


def derive_presence(*, invited: bool, on_leave: bool, present_today: bool) -> str:
    if invited:
        return "none"
    if on_leave:
        return "on_leave"
    if present_today:
        return "present"
    return "absent"


def can_check_in(*, open_session_exists: bool, on_leave: bool) -> None:
    if on_leave:
        raise AttendanceError("Employee is on approved leave.")
    if open_session_exists:
        raise AttendanceError("An open attendance session already exists.")


def can_check_out(*, check_in_at: datetime | None, check_out_at: datetime) -> None:
    if check_in_at is None:
        raise AttendanceError("No open attendance session to close.")
    if check_out_at <= check_in_at:
        raise AttendanceError("Check-out must be after check-in.")


def assert_can_request_correction(*, is_hr: bool, actor_employee_id, session_employee_id) -> None:
    if is_hr:
        return
    if actor_employee_id != session_employee_id:
        raise AttendanceError("Employees can correct only their own attendance.")


def assert_review_decision(*, current_status: str, decision: str, comment: str | None) -> str:
    if current_status != CorrectionStatus.PENDING.value:
        raise AttendanceError("This correction has already been reviewed.")
    normalized = decision.upper()
    if normalized not in {CorrectionStatus.APPROVED.value, CorrectionStatus.REJECTED.value}:
        raise AttendanceError("Decision must be APPROVED or REJECTED.")
    if normalized == CorrectionStatus.REJECTED.value and (not comment or not comment.strip()):
        raise AttendanceError("Rejection requires a comment.")
    return normalized


def worked_minutes(check_in_at: datetime, check_out_at: datetime) -> int:
    return max(0, int((check_out_at - check_in_at).total_seconds() // 60))


NOT_SCHEDULED = "NOT_SCHEDULED"
HALF_DAY_UNITS = Decimal("0.5")
FULL_DAY_UNITS = Decimal("1")
ZERO_UNITS = Decimal("0")
_MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


@dataclass(frozen=True)
class DayPayableInput:
    work_date: date
    scheduled: bool
    status: str | None = None
    on_paid_leave: bool = False
    on_unpaid_leave: bool = False


@dataclass(frozen=True)
class PayableSummary:
    scheduled_days: Decimal
    payable_days: Decimal
    days_present: Decimal
    leave_days: Decimal


def derive_day_status(
    *,
    on_leave: bool,
    worked: int,
    full_day_minutes: int,
    half_day_minutes: int,
    late: bool,
) -> AttendanceStatus:
    if on_leave:
        return AttendanceStatus.LEAVE
    if worked <= 0:
        return AttendanceStatus.ABSENT
    if worked < half_day_minutes:
        return AttendanceStatus.ABSENT
    if worked < full_day_minutes:
        return AttendanceStatus.HALF_DAY
    if late:
        return AttendanceStatus.LATE
    return AttendanceStatus.PRESENT


def extra_minutes(worked: int | None, full_day_minutes: int) -> int:
    if worked is None:
        return 0
    return max(0, int(worked) - int(full_day_minutes))


def parse_year_month(value: str) -> tuple[date, date]:
    match = _MONTH_PATTERN.fullmatch((value or "").strip())
    if match is None:
        raise AttendanceError("Month must be YYYY-MM.")
    year = int(match.group(1))
    month = int(match.group(2))
    try:
        start = date(year, month, 1)
    except ValueError as exc:
        raise AttendanceError("Month must be YYYY-MM.") from exc
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def year_month_label(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def iter_dates(starts_on: date, ends_on: date) -> list[date]:
    if ends_on < starts_on:
        return []
    days: list[date] = []
    cursor = starts_on
    while cursor <= ends_on:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def is_scheduled_workday(day: date, *, workweek: Sequence[int], holidays: set[date]) -> bool:
    return day.weekday() in set(workweek) and day not in holidays


def scheduled_dates(
    starts_on: date,
    ends_on: date,
    *,
    workweek: Sequence[int],
    holidays: set[date],
) -> list[date]:
    return [
        day
        for day in iter_dates(starts_on, ends_on)
        if is_scheduled_workday(day, workweek=workweek, holidays=holidays)
    ]


def payable_units_for_day(
    *,
    scheduled: bool,
    status: str | None,
    on_paid_leave: bool,
    on_unpaid_leave: bool,
) -> Decimal:
    if not scheduled:
        return ZERO_UNITS
    if on_paid_leave:
        return FULL_DAY_UNITS
    if on_unpaid_leave:
        return ZERO_UNITS
    normalized = (status or "").upper()
    if normalized in {AttendanceStatus.PRESENT.value, AttendanceStatus.LATE.value}:
        return FULL_DAY_UNITS
    if normalized == AttendanceStatus.HALF_DAY.value:
        return HALF_DAY_UNITS
    return ZERO_UNITS


def calendar_day_status(
    *,
    scheduled: bool,
    status: str | None,
    on_paid_leave: bool,
    on_unpaid_leave: bool,
) -> str:
    if on_paid_leave or on_unpaid_leave:
        return AttendanceStatus.LEAVE.value
    if status:
        return status
    if not scheduled:
        return NOT_SCHEDULED
    return AttendanceStatus.ABSENT.value


def summarize_payable_days(days: Sequence[DayPayableInput]) -> PayableSummary:
    scheduled = 0
    payable = ZERO_UNITS
    present = ZERO_UNITS
    leave = ZERO_UNITS
    for day in days:
        if not day.scheduled:
            continue
        scheduled += 1
        on_leave = day.on_paid_leave or day.on_unpaid_leave
        if on_leave:
            leave += FULL_DAY_UNITS
        payable += payable_units_for_day(
            scheduled=True,
            status=day.status,
            on_paid_leave=day.on_paid_leave,
            on_unpaid_leave=day.on_unpaid_leave,
        )
        if on_leave:
            continue
        normalized = (day.status or "").upper()
        if normalized in {AttendanceStatus.PRESENT.value, AttendanceStatus.LATE.value}:
            present += FULL_DAY_UNITS
        elif normalized == AttendanceStatus.HALF_DAY.value:
            present += HALF_DAY_UNITS
    return PayableSummary(
        scheduled_days=Decimal(scheduled),
        payable_days=payable,
        days_present=present,
        leave_days=leave,
    )


def payable_summary_for_employee(
    *,
    scheduled: Sequence[date],
    session_status_by_date: dict[date, str],
    paid_leave_dates: set[date],
    unpaid_leave_dates: set[date],
) -> PayableSummary:
    days = [
        DayPayableInput(
            work_date=day,
            scheduled=True,
            status=session_status_by_date.get(day),
            on_paid_leave=day in paid_leave_dates,
            on_unpaid_leave=day in unpaid_leave_dates,
        )
        for day in scheduled
    ]
    return summarize_payable_days(days)


def leave_dates_on_scheduled(
    starts_on: date,
    ends_on: date,
    *,
    scheduled: set[date],
) -> set[date]:
    return {day for day in iter_dates(starts_on, ends_on) if day in scheduled}
