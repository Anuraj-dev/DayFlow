from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.domain.payroll import ComponentKind, PayrollPeriodStatus
from app.domain.roles import EmployeeStatus, Role, UserStatus
from app.models import (
    Employee,
    EmployeeSalaryComponent,
    JobAssignment,
    LeaveBalance,
    LeaveType,
    Organization,
    OrganizationMembership,
    PayrollPeriod,
    PayrollRecord,
    PayrollRecordLine,
    SalaryComponent,
    User,
    WorkPolicy,
)


async def seed_if_empty(session: AsyncSession) -> None:
    existing = await session.scalar(select(Organization).limit(1))
    if existing is not None:
        return

    settings = get_settings()
    org = Organization(name="Dayflow Demo", timezone="Asia/Kolkata", currency="INR")
    session.add(org)
    await session.flush()

    hr_user = User(
        email=settings.seed_hr_email,
        password_hash=hash_password(settings.seed_hr_password),
        email_verified_at=datetime.now(UTC),
        status=UserStatus.ACTIVE.value,
    )
    employee_user = User(
        email=settings.seed_employee_email,
        password_hash=hash_password(settings.seed_employee_password),
        email_verified_at=datetime.now(UTC),
        status=UserStatus.ACTIVE.value,
    )
    session.add_all([hr_user, employee_user])
    await session.flush()

    session.add_all(
        [
            OrganizationMembership(
                organization_id=org.id, user_id=hr_user.id, role=Role.HR.value
            ),
            OrganizationMembership(
                organization_id=org.id, user_id=employee_user.id, role=Role.EMPLOYEE.value
            ),
        ]
    )

    hr_employee = Employee(
        organization_id=org.id,
        user_id=hr_user.id,
        employee_code="HR-001",
        first_name="Asha",
        last_name="Mehta",
        phone="+91-90000-00001",
        address="Dayflow HQ",
        status=EmployeeStatus.ACTIVE.value,
        joined_on=date(2024, 1, 8),
    )
    staff_employee = Employee(
        organization_id=org.id,
        user_id=employee_user.id,
        employee_code="EMP-014",
        first_name="Rohan",
        last_name="Iyer",
        phone="+91-90000-00014",
        address="Bengaluru",
        status=EmployeeStatus.ACTIVE.value,
        joined_on=date(2025, 3, 3),
    )
    session.add_all([hr_employee, staff_employee])
    await session.flush()

    session.add_all(
        [
            JobAssignment(
                employee_id=hr_employee.id,
                title="HR Officer",
                department="People",
                employment_type="FULL_TIME",
                location="Bengaluru",
                starts_on=date(2024, 1, 8),
            ),
            JobAssignment(
                employee_id=staff_employee.id,
                title="Operations Associate",
                department="Operations",
                employment_type="FULL_TIME",
                location="Bengaluru",
                starts_on=date(2025, 3, 3),
            ),
            WorkPolicy(organization_id=org.id),
        ]
    )

    paid = LeaveType(
        organization_id=org.id,
        name="Paid leave",
        code="PAID",
        is_paid=True,
        requires_balance=True,
    )
    sick = LeaveType(
        organization_id=org.id,
        name="Sick leave",
        code="SICK",
        is_paid=True,
        requires_balance=True,
    )
    unpaid = LeaveType(
        organization_id=org.id,
        name="Unpaid leave",
        code="UNPAID",
        is_paid=False,
        requires_balance=False,
    )
    session.add_all([paid, sick, unpaid])
    await session.flush()

    year_start, year_end = date(2026, 1, 1), date(2026, 12, 31)
    for employee in (hr_employee, staff_employee):
        session.add_all(
            [
                LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=paid.id,
                    period_start=year_start,
                    period_end=year_end,
                    granted_days=18,
                ),
                LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=sick.id,
                    period_start=year_start,
                    period_end=year_end,
                    granted_days=8,
                ),
                LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=unpaid.id,
                    period_start=year_start,
                    period_end=year_end,
                    granted_days=0,
                ),
            ]
        )

    basic = SalaryComponent(
        organization_id=org.id,
        name="Basic",
        code="BASIC",
        kind=ComponentKind.EARNING.value,
    )
    hra = SalaryComponent(
        organization_id=org.id,
        name="House rent allowance",
        code="HRA",
        kind=ComponentKind.EARNING.value,
    )
    pf = SalaryComponent(
        organization_id=org.id,
        name="Provident fund",
        code="PF",
        kind=ComponentKind.DEDUCTION.value,
        taxable=False,
    )
    session.add_all([basic, hra, pf])
    await session.flush()

    session.add_all(
        [
            EmployeeSalaryComponent(
                employee_id=staff_employee.id,
                salary_component_id=basic.id,
                amount=Decimal("40000.00"),
                effective_from=date(2025, 3, 3),
            ),
            EmployeeSalaryComponent(
                employee_id=staff_employee.id,
                salary_component_id=hra.id,
                amount=Decimal("16000.00"),
                effective_from=date(2025, 3, 3),
            ),
            EmployeeSalaryComponent(
                employee_id=staff_employee.id,
                salary_component_id=pf.id,
                amount=Decimal("4800.00"),
                effective_from=date(2025, 3, 3),
            ),
        ]
    )

    period = PayrollPeriod(
        organization_id=org.id,
        starts_on=date(2026, 7, 1),
        ends_on=date(2026, 7, 31),
        pay_date=date(2026, 8, 5),
        status=PayrollPeriodStatus.PUBLISHED.value,
        finalized_by=hr_user.id,
        finalized_at=datetime(2026, 8, 1, tzinfo=UTC),
        published_at=datetime(2026, 8, 2, tzinfo=UTC),
    )
    session.add(period)
    await session.flush()

    record = PayrollRecord(
        payroll_period_id=period.id,
        employee_id=staff_employee.id,
        gross_amount=Decimal("56000.00"),
        deduction_amount=Decimal("4800.00"),
        net_amount=Decimal("51200.00"),
        currency="INR",
        published_at=period.published_at,
    )
    session.add(record)
    await session.flush()
    session.add_all(
        [
            PayrollRecordLine(
                payroll_record_id=record.id,
                salary_component_id=basic.id,
                label_snapshot="Basic",
                amount=Decimal("40000.00"),
            ),
            PayrollRecordLine(
                payroll_record_id=record.id,
                salary_component_id=hra.id,
                label_snapshot="House rent allowance",
                amount=Decimal("16000.00"),
            ),
            PayrollRecordLine(
                payroll_record_id=record.id,
                salary_component_id=pf.id,
                label_snapshot="Provident fund",
                amount=Decimal("-4800.00"),
            ),
        ]
    )
    await session.commit()
