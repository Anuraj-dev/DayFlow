from datetime import date, timedelta
from enum import StrEnum


class LeaveRequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class LeaveError(ValueError):
    pass


def ranges_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def counted_days(
    starts_on: date,
    ends_on: date,
    *,
    weekend_weekdays: set[int],
    holidays: set[date],
) -> int:
    if ends_on < starts_on:
        raise LeaveError("Leave end date must be on or after the start date.")
    total = 0
    cursor = starts_on
    while cursor <= ends_on:
        if cursor.weekday() not in weekend_weekdays and cursor not in holidays:
            total += 1
        cursor += timedelta(days=1)
    return total


def remaining_balance(*, granted: float, used: float, adjustment: float) -> float:
    return granted + adjustment - used


def assert_can_submit(
    *,
    counted: int,
    remaining: float,
    requires_balance: bool,
    overlaps_existing: bool,
) -> None:
    if counted <= 0:
        raise LeaveError("Leave request does not include any countable workdays.")
    if overlaps_existing:
        raise LeaveError("Leave range overlaps a pending or approved request.")
    if requires_balance and counted > remaining:
        raise LeaveError("Insufficient leave balance.")


def assert_rejection_comment(comment: str | None) -> None:
    if not comment or not comment.strip():
        raise LeaveError("Rejection requires a comment.")


def assert_can_cancel(*, current_status: str, is_owner: bool) -> None:
    if not is_owner:
        raise LeaveError("Employees can cancel only their own pending requests.")
    if current_status != LeaveRequestStatus.PENDING.value:
        raise LeaveError("Only pending leave requests can be cancelled.")


def assert_can_review(*, current_status: str, decision: str, comment: str | None) -> str:
    if current_status != LeaveRequestStatus.PENDING.value:
        raise LeaveError("This leave request is not pending.")
    normalized = decision.upper()
    if normalized not in {LeaveRequestStatus.APPROVED.value, LeaveRequestStatus.REJECTED.value}:
        raise LeaveError("Decision must be APPROVED or REJECTED.")
    if normalized == LeaveRequestStatus.REJECTED.value:
        assert_rejection_comment(comment)
    return normalized
