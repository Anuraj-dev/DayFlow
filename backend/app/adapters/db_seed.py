from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.salary import assign_default_salary
from app.core.config import get_settings
from app.core.security import hash_password
from app.domain.leave import DEFAULT_LEAVE_GRANTS
from app.domain.payroll import PayrollPeriodStatus, signed_line_amount
from app.domain.roles import EmployeeStatus, Role, UserStatus
from app.models import (
    Employee,
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

    demo_profiles = [
        ("OINEKA20250015", "Neha", "Kapoor", "+91-90000-00015", "Mumbai", date(2025, 6, 9), "Product Designer", "Product"),
        ("OIVISI20240016", "Vikram", "Singh", "+91-90000-00016", "Delhi", date(2024, 11, 18), "Finance Analyst", "Finance"),
        ("OISAKA20250017", "Sara", "Khan", "+91-90000-00017", "Hyderabad", date(2025, 8, 4), "Customer Success Lead", "Customer Success"),
        ("OIARNA20260018", "Arjun", "Nair", "+91-90000-00018", "Bengaluru", date(2026, 1, 12), "Backend Engineer", "Engineering"),
    ]
    demo_people = [
        Employee(
            organization_id=org.id,
            employee_code=code,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            address=location,
            status=EmployeeStatus.ACTIVE.value,
            joined_on=joined_on,
        )
        for code, first_name, last_name, phone, location, joined_on, _title, _department in demo_profiles
    ]
    session.add_all(demo_people)
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
    session.add_all(
        [
            JobAssignment(
                employee_id=employee.id,
                title=title,
                department=department,
                employment_type="FULL_TIME",
                location=location,
                starts_on=employee.joined_on,
            )
            for employee, (
                _code,
                _first_name,
                _last_name,
                _phone,
                location,
                _joined_on,
                title,
                department,
            ) in zip(demo_people, demo_profiles, strict=True)
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
    for employee in (hr_employee, staff_employee, *demo_people):
        session.add_all(
            [
                LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=paid.id,
                    period_start=year_start,
                    period_end=year_end,
                    granted_days=DEFAULT_LEAVE_GRANTS["PAID"],
                ),
                LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=sick.id,
                    period_start=year_start,
                    period_end=year_end,
                    granted_days=DEFAULT_LEAVE_GRANTS["SICK"],
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

    computed = await assign_default_salary(
        session,
        organization_id=org.id,
        employee_id=staff_employee.id,
        effective_from=date(2025, 3, 3),
    )
    for employee in demo_people:
        await assign_default_salary(
            session,
            organization_id=org.id,
            employee_id=employee.id,
            effective_from=employee.joined_on or date(2026, 1, 1),
        )
    components = {
        component.code.upper(): component
        for component in (
            await session.scalars(select(SalaryComponent).where(SalaryComponent.organization_id == org.id))
        ).all()
    }

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
        gross_amount=computed.gross_amount,
        deduction_amount=computed.deduction_amount,
        net_amount=computed.net_amount,
        currency="INR",
        published_at=period.published_at,
    )
    session.add(record)
    await session.flush()
    session.add_all(
        [
            PayrollRecordLine(
                payroll_record_id=record.id,
                salary_component_id=components[line.code].id,
                label_snapshot=line.name,
                amount=signed_line_amount(line.kind, line.amount),
            )
            for line in computed.lines
        ]
    )
    await session.commit()
