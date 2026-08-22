from datetime import datetime
from enum import StrEnum


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
