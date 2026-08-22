from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.domain.attendance import (
    AttendanceError,
    AttendanceStatus,
    DayPayableInput,
    can_check_in,
    can_check_out,
    derive_day_status,
    derive_presence,
    extra_minutes,
    parse_year_month,
    payable_units_for_day,
    scheduled_dates,
    summarize_payable_days,
)
from app.domain.identity import (
    IdentityError,
    assert_employee_patch_allowed,
    build_employee_code,
    can_edit_employee,
    can_read_employee,
    can_read_private_employee_fields,
)
from app.domain.leave import (
    DEFAULT_LEAVE_GRANTS,
    LeaveError,
    assert_can_submit,
    assert_certificate_allowed,
    assert_rejection_comment,
    can_download_certificate,
    counted_days,
    ranges_overlap,
    sniff_certificate,
)
from app.domain.payroll import (
    CalculationType,
    ComponentKind,
    PayrollError,
    PayrollPeriodStatus,
    SalaryStructureLine,
    assert_mutable,
    assert_no_attendance_blockers,
    compute_salary,
    default_salary_structure,
    net_amount,
    prorate_computed_salary,
)
from app.domain.roles import Role


def test_build_employee_code_matches_board_format():
    assert build_employee_code(first_name="Jo", last_name="Do", year=2022, serial=1) == "OIJODO20220001"


def test_derive_presence_prefers_leave_then_present():
    assert derive_presence(invited=True, on_leave=False, present_today=False) == "none"
    assert derive_presence(invited=False, on_leave=True, present_today=True) == "on_leave"
    assert derive_presence(invited=False, on_leave=False, present_today=True) == "present"
    assert derive_presence(invited=False, on_leave=False, present_today=False) == "absent"


def test_directory_is_readable_by_employees():
    assert can_read_employee(role=Role.EMPLOYEE, actor_employee_id=1, target_employee_id=1)
    assert can_read_employee(role=Role.EMPLOYEE, actor_employee_id=1, target_employee_id=2)
    assert can_read_employee(role=Role.HR, actor_employee_id=1, target_employee_id=2)


def test_employee_patch_field_permissions():
    assert can_edit_employee(role=Role.EMPLOYEE, actor_employee_id=1, target_employee_id=1)
    assert not can_edit_employee(role=Role.EMPLOYEE, actor_employee_id=1, target_employee_id=2)
    assert can_edit_employee(role=Role.HR, actor_employee_id=1, target_employee_id=2)
    assert_employee_patch_allowed(role=Role.EMPLOYEE, fields={"phone", "address"})
    with pytest.raises(IdentityError):
        assert_employee_patch_allowed(role=Role.EMPLOYEE, fields={"title"})
    with pytest.raises(IdentityError, match="pan"):
        assert_employee_patch_allowed(role=Role.EMPLOYEE, fields={"pan"})
    assert_employee_patch_allowed(role=Role.HR, fields={"title", "department", "employment_type"})
    assert_employee_patch_allowed(
        role=Role.HR,
        fields={"date_of_birth", "personal_email", "pan", "bank_account_number", "ifsc", "uan"},
    )
    assert can_read_private_employee_fields(
        role=Role.EMPLOYEE, actor_employee_id=1, target_employee_id=1
    )
    assert not can_read_private_employee_fields(
        role=Role.EMPLOYEE, actor_employee_id=1, target_employee_id=2
    )
    assert can_read_private_employee_fields(
        role=Role.HR, actor_employee_id=1, target_employee_id=2
    )


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
    assert DEFAULT_LEAVE_GRANTS == {"PAID": 24.0, "SICK": 7.0, "UNPAID": 0.0}
    assert_certificate_allowed(leave_type_code="SICK", has_file=True)
    with pytest.raises(LeaveError, match="sick leave"):
        assert_certificate_allowed(leave_type_code="PAID", has_file=True)
    content_type, suffix = sniff_certificate(b"%PDF-1.4 sample")
    assert content_type == "application/pdf"
    assert suffix == ".pdf"
    with pytest.raises(LeaveError, match="PDF, JPEG, or PNG"):
        sniff_certificate(b"not-a-certificate")
    assert can_download_certificate(role=Role.HR, actor_employee_id=1, request_employee_id=2)
    assert can_download_certificate(role=Role.EMPLOYEE, actor_employee_id=1, request_employee_id=1)
    assert not can_download_certificate(role=Role.EMPLOYEE, actor_employee_id=1, request_employee_id=2)


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


def _line_amount(result, code: str) -> Decimal:
    return next(line.amount for line in result.lines if line.code == code)


def test_default_wage_split_uses_board_literals():
    result = compute_salary(Decimal("50000.00"), default_salary_structure())
    assert result.monthly_wage == Decimal("50000.00")
    assert _line_amount(result, "BASIC") == Decimal("25000.00")
    assert _line_amount(result, "HRA") == Decimal("12500.00")
    assert _line_amount(result, "STD_ALLOW") == Decimal("4167.00")
    assert _line_amount(result, "PERF_BONUS") == Decimal("4165.00")
    assert _line_amount(result, "LTA") == Decimal("4165.00")
    assert _line_amount(result, "FIXED_ALLOW") == Decimal("3.00")
    assert _line_amount(result, "PF") == Decimal("3000.00")
    assert _line_amount(result, "PF_EMPLOYER") == Decimal("3000.00")
    assert _line_amount(result, "PT") == Decimal("200.00")
    earning_total = sum(
        (line.amount for line in result.lines if line.kind is ComponentKind.EARNING),
        Decimal("0.00"),
    )
    assert earning_total == Decimal("50000.00")
    remainder = next(line for line in result.lines if line.code == "FIXED_ALLOW")
    assert remainder.editable is False
    assert remainder.calculation_type is CalculationType.REMAINDER


def test_employee_pf_and_pt_reduce_net_employer_pf_does_not():
    result = compute_salary(Decimal("50000.00"), default_salary_structure())
    assert result.gross_amount == Decimal("50000.00")
    assert result.deduction_amount == Decimal("3200.00")
    assert result.net_amount == Decimal("46800.00")
    assert result.employer_amount == Decimal("3000.00")
    employer = next(line for line in result.lines if line.code == "PF_EMPLOYER")
    assert employer.kind is ComponentKind.EMPLOYER
    assert employer.editable is False


def test_wage_change_recomputes_derived_amounts():
    result = compute_salary(Decimal("60000.00"), default_salary_structure())
    assert _line_amount(result, "BASIC") == Decimal("30000.00")
    assert _line_amount(result, "HRA") == Decimal("15000.00")
    assert _line_amount(result, "STD_ALLOW") == Decimal("4167.00")
    assert _line_amount(result, "PERF_BONUS") == Decimal("4998.00")
    assert _line_amount(result, "LTA") == Decimal("4998.00")
    assert _line_amount(result, "FIXED_ALLOW") == Decimal("837.00")
    assert _line_amount(result, "PF") == Decimal("3600.00")
    assert result.net_amount == Decimal("56200.00")


def test_components_exceeding_wage_are_rejected():
    structure = [
        line
        if line.code != "STD_ALLOW"
        else SalaryStructureLine(
            code=line.code,
            name=line.name,
            kind=line.kind,
            calculation_type=line.calculation_type,
            rate=line.rate,
            amount=Decimal("20000.00"),
        )
        for line in default_salary_structure()
    ]
    with pytest.raises(PayrollError, match="exceed"):
        compute_salary(Decimal("50000.00"), structure)


def test_negative_values_and_cycles_are_rejected():
    with pytest.raises(PayrollError, match="negative"):
        compute_salary(Decimal("-1.00"), default_salary_structure())
    with pytest.raises(PayrollError, match="negative"):
        compute_salary(
            Decimal("50000.00"),
            [
                SalaryStructureLine(
                    code="BASIC",
                    name="Basic",
                    kind=ComponentKind.EARNING,
                    calculation_type=CalculationType.PERCENT_OF_WAGE,
                    rate=Decimal("-50.00"),
                )
            ],
        )
    cyclic = [
        SalaryStructureLine(
            code="BASIC",
            name="Basic",
            kind=ComponentKind.EARNING,
            calculation_type=CalculationType.PERCENT_OF_BASIC,
            rate=Decimal("50.00"),
        )
    ]
    with pytest.raises(PayrollError, match="cycle"):
        compute_salary(Decimal("50000.00"), cyclic)
    bonus_of_basic = [
        SalaryStructureLine(
            code="BASIC",
            name="Basic",
            kind=ComponentKind.EARNING,
            calculation_type=CalculationType.PERCENT_OF_WAGE,
            rate=Decimal("50.00"),
        ),
        SalaryStructureLine(
            code="PERF_BONUS",
            name="Performance Bonus",
            kind=ComponentKind.EARNING,
            calculation_type=CalculationType.PERCENT_OF_BASIC,
            rate=Decimal("10.00"),
        ),
    ]
    with pytest.raises(PayrollError, match="HRA"):
        compute_salary(Decimal("50000.00"), bonus_of_basic)


def test_extra_minutes_are_only_the_overflow_past_a_full_day():
    assert extra_minutes(None, 480) == 0
    assert extra_minutes(480, 480) == 0
    assert extra_minutes(420, 480) == 0
    assert extra_minutes(540, 480) == 60


def test_parse_year_month_and_scheduled_days_skip_weekends_and_holidays():
    start, end = parse_year_month("2026-08")
    assert start == date(2026, 8, 1)
    assert end == date(2026, 8, 31)
    with pytest.raises(AttendanceError, match="YYYY-MM"):
        parse_year_month("2026/08")
    days = scheduled_dates(
        date(2026, 8, 10),
        date(2026, 8, 16),
        workweek=[0, 1, 2, 3, 4],
        holidays={date(2026, 8, 12)},
    )
    assert days == [date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 13), date(2026, 8, 14)]


def test_payable_days_count_half_day_paid_leave_unpaid_leave_and_missing():
    assert payable_units_for_day(
        scheduled=True, status=AttendanceStatus.PRESENT.value, on_paid_leave=False, on_unpaid_leave=False
    ) == Decimal("1")
    assert payable_units_for_day(
        scheduled=True, status=AttendanceStatus.LATE.value, on_paid_leave=False, on_unpaid_leave=False
    ) == Decimal("1")
    assert payable_units_for_day(
        scheduled=True, status=AttendanceStatus.HALF_DAY.value, on_paid_leave=False, on_unpaid_leave=False
    ) == Decimal("0.5")
    assert payable_units_for_day(
        scheduled=True, status=AttendanceStatus.ABSENT.value, on_paid_leave=True, on_unpaid_leave=False
    ) == Decimal("1")
    assert payable_units_for_day(
        scheduled=True, status=None, on_paid_leave=False, on_unpaid_leave=True
    ) == Decimal("0")
    assert payable_units_for_day(
        scheduled=True, status=None, on_paid_leave=False, on_unpaid_leave=False
    ) == Decimal("0")

    summary = summarize_payable_days(
        [
            DayPayableInput(work_date=date(2026, 8, 10), scheduled=True, status="PRESENT"),
            DayPayableInput(work_date=date(2026, 8, 11), scheduled=True, status="HALF_DAY"),
            DayPayableInput(work_date=date(2026, 8, 12), scheduled=False, status=None),
            DayPayableInput(
                work_date=date(2026, 8, 13),
                scheduled=True,
                status="ABSENT",
                on_paid_leave=True,
            ),
            DayPayableInput(
                work_date=date(2026, 8, 14),
                scheduled=True,
                status=None,
                on_unpaid_leave=True,
            ),
            DayPayableInput(work_date=date(2026, 8, 15), scheduled=False),
        ]
    )
    assert summary.scheduled_days == Decimal("4")
    assert summary.payable_days == Decimal("2.5")
    assert summary.days_present == Decimal("1.5")
    assert summary.leave_days == Decimal("2")


def test_prorate_earnings_by_payable_days_recomputes_pf_keeps_professional_tax():
    full = compute_salary(Decimal("50000.00"), default_salary_structure())
    prorated = prorate_computed_salary(full, payable_days=Decimal("20"), scheduled_days=Decimal("22"))
    assert _line_amount(prorated, "BASIC") == Decimal("22727.27")
    assert _line_amount(prorated, "HRA") == Decimal("11363.64")
    assert _line_amount(prorated, "PF") == Decimal("2727.27")
    assert _line_amount(prorated, "PF_EMPLOYER") == Decimal("2727.27")
    assert _line_amount(prorated, "PT") == Decimal("200.00")
    assert _line_amount(prorated, "PF") == (Decimal("22727.27") * Decimal("0.12")).quantize(Decimal("0.01"))
    unchanged = prorate_computed_salary(full, payable_days=Decimal("22"), scheduled_days=Decimal("22"))
    assert unchanged.gross_amount == full.gross_amount
    assert unchanged.net_amount == full.net_amount
    with pytest.raises(PayrollError, match="scheduled working days"):
        prorate_computed_salary(full, payable_days=Decimal("0"), scheduled_days=Decimal("0"))


def test_open_sessions_and_pending_corrections_block_finalization():
    assert_no_attendance_blockers(open_session_count=0, pending_correction_count=0)
    with pytest.raises(PayrollError, match="Open attendance sessions"):
        assert_no_attendance_blockers(open_session_count=1, pending_correction_count=0)
    with pytest.raises(PayrollError, match="Pending attendance corrections"):
        assert_no_attendance_blockers(open_session_count=0, pending_correction_count=1)
