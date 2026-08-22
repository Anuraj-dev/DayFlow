from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.domain.attendance import AttendanceError, can_check_in, can_check_out, derive_day_status
from app.domain.identity import can_read_employee
from app.domain.leave import (
    LeaveError,
    assert_can_submit,
    assert_rejection_comment,
    counted_days,
    ranges_overlap,
)
from app.domain.payroll import PayrollError, PayrollPeriodStatus, assert_mutable, net_amount
from app.domain.roles import Role


def test_employee_cannot_read_another_record():
    assert can_read_employee(role=Role.EMPLOYEE, actor_employee_id=1, target_employee_id=1)
    assert not can_read_employee(role=Role.EMPLOYEE, actor_employee_id=1, target_employee_id=2)
    assert can_read_employee(role=Role.HR, actor_employee_id=1, target_employee_id=2)


def test_open_session_blocks_check_in():
    with pytest.raises(AttendanceError):
        can_check_in(open_session_exists=True, on_leave=False)
    with pytest.raises(AttendanceError):
        can_check_in(open_session_exists=False, on_leave=True)
    can_check_in(open_session_exists=False, on_leave=False)


def test_check_out_must_follow_check_in():
    start = datetime(2026, 8, 22, 9, 0, tzinfo=UTC)
    with pytest.raises(AttendanceError):
        can_check_out(check_in_at=start, check_out_at=start)
    can_check_out(check_in_at=start, check_out_at=datetime(2026, 8, 22, 18, 0, tzinfo=UTC))


def test_leave_overlap_and_weekends():
    assert ranges_overlap(date(2026, 8, 10), date(2026, 8, 12), date(2026, 8, 12), date(2026, 8, 14))
    # Saturday-Sunday excluded when weekend_weekdays is 5,6
    days = counted_days(
        date(2026, 8, 21),
        date(2026, 8, 24),
        weekend_weekdays={5, 6},
        holidays=set(),
    )
    assert days == 2
    with pytest.raises(LeaveError):
        assert_can_submit(counted=1, remaining=0, requires_balance=True, overlaps_existing=False)
    with pytest.raises(LeaveError):
        assert_rejection_comment("")
    assert_rejection_comment("Missing coverage")


def test_finalized_payroll_is_immutable():
    assert net_amount(Decimal("56000"), Decimal("4800")) == Decimal("51200")
    with pytest.raises(PayrollError):
        assert_mutable(PayrollPeriodStatus.FINALIZED)
    derive_day_status(
        on_leave=False,
        worked=480,
        full_day_minutes=480,
        half_day_minutes=240,
        late=False,
    )
