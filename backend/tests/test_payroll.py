from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.domain.payroll import PayrollPeriodStatus
from app.domain.roles import EmployeeStatus, Role, UserStatus
from app.adapters.salary import assign_default_salary
from app.domain.attendance import scheduled_dates
from app.models import (
    AttendanceSession,
    AuditEvent,
    Employee,
    Holiday,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    Organization,
    OrganizationMembership,
    PayrollPeriod,
    PayrollRecord,
    User,
    WorkPolicy,
)

PASSWORD = "ChangeMe_Emp12!"


async def _sign_in(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post("/api/auth/sign-in", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()


def _select_org():
    return select(Organization).where(Organization.name == "Dayflow Demo")


async def test_employee_get_returns_only_own_published_records(client: AsyncClient):
    suffix = uuid4().hex[:8]
    unpublished_id = None
    draft_period_id = None
    foreign_period_id = None
    other_employee_id = None

    async with SessionLocal() as session:
        org = await session.scalar(_select_org())
        assert org is not None
        hr = await session.scalar(select(Employee).where(Employee.employee_code == "HR-001"))
        assert hr is not None
        other_employee_id = str(hr.id)

        draft = PayrollPeriod(
            organization_id=org.id,
            starts_on=date(2026, 8, 1),
            ends_on=date(2026, 8, 31),
            pay_date=date(2026, 9, 5),
            status=PayrollPeriodStatus.DRAFT.value,
        )
        session.add(draft)
        await session.flush()
        draft_period_id = str(draft.id)
        unpublished = PayrollRecord(
            payroll_period_id=draft.id,
            employee_id=hr.id,
            gross_amount=Decimal("80000.00"),
            deduction_amount=Decimal("6000.00"),
            net_amount=Decimal("74000.00"),
            currency="INR",
            published_at=None,
        )
        session.add(unpublished)
        await session.flush()
        unpublished_id = str(unpublished.id)

        other_org = Organization(name=f"Other Co Payroll {suffix}", timezone="Asia/Kolkata", currency="INR")
        session.add(other_org)
        await session.flush()
        other_hr = User(
            email=f"hr.pay.{suffix}@dayflow.demo",
            password_hash=hash_password(PASSWORD),
            email_verified_at=datetime.now(UTC),
            status=UserStatus.ACTIVE.value,
        )
        session.add(other_hr)
        await session.flush()
        session.add(
            OrganizationMembership(
                organization_id=other_org.id,
                user_id=other_hr.id,
                role=Role.HR.value,
            )
        )
        foreign_employee = Employee(
            organization_id=other_org.id,
            user_id=other_hr.id,
            employee_code=f"XP-{suffix[:4].upper()}",
            first_name="Foreign",
            last_name="Pay",
            status=EmployeeStatus.ACTIVE.value,
            joined_on=date(2026, 1, 1),
        )
        session.add(foreign_employee)
        await session.flush()
        foreign_period = PayrollPeriod(
            organization_id=other_org.id,
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 31),
            pay_date=date(2026, 8, 5),
            status=PayrollPeriodStatus.PUBLISHED.value,
            published_at=datetime(2026, 8, 2, tzinfo=UTC),
        )
        session.add(foreign_period)
        await session.flush()
        foreign_period_id = str(foreign_period.id)
        session.add(
            PayrollRecord(
                payroll_period_id=foreign_period.id,
                employee_id=foreign_employee.id,
                gross_amount=Decimal("10000.00"),
                deduction_amount=Decimal("0.00"),
                net_amount=Decimal("10000.00"),
                currency="INR",
                published_at=foreign_period.published_at,
            )
        )
        await session.commit()

    employee = await _sign_in(client, "employee@dayflow.demo", PASSWORD)
    employee_id = employee["user"]["employee_id"]
    employee_headers = {"Authorization": f"Bearer {employee['access_token']}"}

    listed = await client.get("/api/payroll", headers=employee_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["role"] == "EMPLOYEE"
    period_ids = {row["id"] for row in body["periods"]}
    record_ids = {row["id"] for row in body["records"]}
    assert draft_period_id not in period_ids
    assert foreign_period_id not in period_ids
    assert unpublished_id not in record_ids
    assert body["records"]
    for row in body["records"]:
        assert row["employee_id"] == employee_id
        assert row["published_at"] is not None
        assert row["net_amount"] == "46800.00"
        assert row["currency"] == "INR"

    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    hr_headers = {"Authorization": f"Bearer {hr['access_token']}"}
    hr_listed = await client.get("/api/payroll", headers=hr_headers)
    assert hr_listed.status_code == 200
    hr_body = hr_listed.json()
    assert hr_body["role"] == "HR"
    hr_period_ids = {row["id"] for row in hr_body["periods"]}
    hr_record_ids = {row["id"] for row in hr_body["records"]}
    assert draft_period_id in hr_period_ids
    assert foreign_period_id not in hr_period_ids
    assert unpublished_id in hr_record_ids
    hr_employee_ids = {row["employee_id"] for row in hr_body["records"]}
    assert employee_id in hr_employee_ids
    assert other_employee_id in hr_employee_ids


async def _draft_period_for_demo() -> str:
    async with SessionLocal() as session:
        org = await session.scalar(_select_org())
        assert org is not None
        existing = await session.scalar(
            select(PayrollPeriod).where(
                PayrollPeriod.organization_id == org.id,
                PayrollPeriod.status == PayrollPeriodStatus.DRAFT.value,
                PayrollPeriod.starts_on == date(2026, 9, 1),
            )
        )
        if existing is not None:
            return str(existing.id)
        period = PayrollPeriod(
            organization_id=org.id,
            starts_on=date(2026, 9, 1),
            ends_on=date(2026, 9, 30),
            pay_date=date(2026, 10, 5),
            status=PayrollPeriodStatus.DRAFT.value,
        )
        session.add(period)
        await session.commit()
        return str(period.id)


async def _ensure_present_days(employee_id: str, starts_on: date, ends_on: date) -> None:
    async with SessionLocal() as session:
        org = await session.scalar(_select_org())
        assert org is not None
        policy = await session.scalar(select(WorkPolicy).where(WorkPolicy.organization_id == org.id))
        workweek = policy.workweek if policy and policy.workweek else [0, 1, 2, 3, 4]
        holidays = set(await session.scalars(select(Holiday.date).where(Holiday.organization_id == org.id)))
        people = {employee_id}
        people.update(
            str(row)
            for row in await session.scalars(select(Employee.id).where(Employee.organization_id == org.id))
        )
        days = scheduled_dates(starts_on, ends_on, workweek=workweek, holidays=holidays)
        open_rows = list(
            await session.scalars(
                select(AttendanceSession)
                .join(Employee, Employee.id == AttendanceSession.employee_id)
                .where(
                    Employee.organization_id == org.id,
                    AttendanceSession.status == "OPEN",
                    AttendanceSession.work_date >= starts_on,
                    AttendanceSession.work_date <= ends_on,
                )
            )
        )
        for row in open_rows:
            row.check_out_at = datetime(
                row.work_date.year, row.work_date.month, row.work_date.day, 12, 30, tzinfo=UTC
            )
            row.status = "PRESENT"
            row.worked_minutes = 540
        for person_id in people:
            existing = set(
                await session.scalars(
                    select(AttendanceSession.work_date).where(
                        AttendanceSession.employee_id == person_id,
                        AttendanceSession.work_date >= starts_on,
                        AttendanceSession.work_date <= ends_on,
                    )
                )
            )
            for day in days:
                if day in existing:
                    continue
                session.add(
                    AttendanceSession(
                        employee_id=person_id,
                        work_date=day,
                        check_in_at=datetime(day.year, day.month, day.day, 3, 30, tzinfo=UTC),
                        check_out_at=datetime(day.year, day.month, day.day, 12, 30, tzinfo=UTC),
                        source="SERVER",
                        status="PRESENT",
                        worked_minutes=540,
                    )
                )
        await session.commit()


def _salary_url(employee_id: str) -> str:
    return f"/api/payroll/employees/{employee_id}/salary"


def _line_map(body: dict) -> dict[str, dict]:
    return {row["code"]: row for row in body["lines"]}


async def test_hr_patches_wage_recomputes_derived_lines(client: AsyncClient):
    employee = await _sign_in(client, "employee@dayflow.demo", PASSWORD)
    employee_id = employee["user"]["employee_id"]
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {hr['access_token']}"}

    current = await client.get(_salary_url(employee_id), headers=headers, params={"as_of": "2026-08-31"})
    assert current.status_code == 200
    assert current.json()["monthly_wage"] == "50000.00"
    assert _line_map(current.json())["BASIC"]["amount"] == "25000.00"

    patched = await client.patch(
        _salary_url(employee_id),
        headers=headers,
        json={"monthly_wage": "60000.00", "effective_from": "2026-11-01"},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["employee_id"] == employee_id
    assert body["monthly_wage"] == "60000.00"
    lines = _line_map(body)
    assert lines["BASIC"]["amount"] == "30000.00"
    assert lines["HRA"]["amount"] == "15000.00"
    assert lines["STD_ALLOW"]["amount"] == "4167.00"
    assert lines["PERF_BONUS"]["amount"] == "4998.00"
    assert lines["LTA"]["amount"] == "4998.00"
    assert lines["FIXED_ALLOW"]["amount"] == "837.00"
    assert lines["FIXED_ALLOW"]["editable"] is False
    assert lines["PF"]["amount"] == "3600.00"
    assert lines["PF_EMPLOYER"]["amount"] == "3600.00"
    assert lines["PT"]["amount"] == "200.00"
    assert body["net_amount"] == "56200.00"
    assert body["employer_amount"] == "3600.00"

    prior = await client.get(_salary_url(employee_id), headers=headers, params={"as_of": "2026-09-30"})
    assert prior.status_code == 200
    assert prior.json()["monthly_wage"] == "50000.00"
    assert _line_map(prior.json())["BASIC"]["amount"] == "25000.00"

    over = await client.patch(
        _salary_url(employee_id),
        headers=headers,
        json={
            "effective_from": "2026-11-01",
            "components": [{"code": "STD_ALLOW", "amount": "20000.00"}],
        },
    )
    assert over.status_code == 400
    assert "exceed" in over.json()["detail"]

    async with SessionLocal() as session:
        audit = await session.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "employee_salary",
                AuditEvent.action == "payroll.salary.update",
                AuditEvent.entity_id == employee_id,
            )
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit is not None
        assert audit.organization_id is not None
        assert audit.after_json is not None
        assert audit.after_json["monthly_wage"] == "60000.00"


async def test_employee_cannot_patch_salary(client: AsyncClient):
    employee = await _sign_in(client, "employee@dayflow.demo", PASSWORD)
    headers = {"Authorization": f"Bearer {employee['access_token']}"}
    patched = await client.patch(
        _salary_url(employee["user"]["employee_id"]),
        headers=headers,
        json={"monthly_wage": "1.00"},
    )
    assert patched.status_code == 403
    assert patched.json()["detail"] == "HR role required."


async def test_employee_reads_own_salary_not_coworker(client: AsyncClient):
    employee = await _sign_in(client, "employee@dayflow.demo", PASSWORD)
    headers = {"Authorization": f"Bearer {employee['access_token']}"}
    own = await client.get(
        _salary_url(employee["user"]["employee_id"]),
        headers=headers,
        params={"as_of": "2026-08-31"},
    )
    assert own.status_code == 200
    body = own.json()
    assert body["monthly_wage"] == "50000.00"
    assert _line_map(body)["BASIC"]["amount"] == "25000.00"
    assert body["employee_id"] == employee["user"]["employee_id"]

    async with SessionLocal() as session:
        hr_employee = await session.scalar(select(Employee).where(Employee.employee_code == "HR-001"))
        assert hr_employee is not None
        coworker_id = str(hr_employee.id)

    hidden = await client.get(_salary_url(coworker_id), headers=headers)
    assert hidden.status_code == 403
    assert hidden.json()["detail"] == "Salary is visible only to HR or the employee."

    coworker_patch = await client.patch(
        _salary_url(coworker_id),
        headers=headers,
        json={"monthly_wage": "1.00"},
    )
    assert coworker_patch.status_code == 403
    assert coworker_patch.json()["detail"] == "HR role required."


async def test_hr_finalize_snapshots_salary_and_locks_period(client: AsyncClient):
    period_id = await _draft_period_for_demo()
    employee = await _sign_in(client, "employee@dayflow.demo", PASSWORD)
    employee_id = employee["user"]["employee_id"]
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {hr['access_token']}"}

    salary = await client.get(_salary_url(employee_id), headers=headers, params={"as_of": "2026-09-30"})
    assert salary.status_code == 200
    assert salary.json()["monthly_wage"] == "50000.00"
    await _ensure_present_days(employee_id, date(2026, 9, 1), date(2026, 9, 30))

    finalized = await client.post(f"/api/payroll/periods/{period_id}/finalize", headers=headers)
    assert finalized.status_code == 200
    body = finalized.json()
    assert body["id"] == period_id
    assert body["status"] == "FINALIZED"
    assert body["starts_on"] == "2026-09-01"
    assert body["ends_on"] == "2026-09-30"
    assert body["pay_date"] == "2026-10-05"
    record = next(row for row in body["records"] if row["employee_id"] == employee_id)
    assert record["gross_amount"] == "50000.00"
    assert record["deduction_amount"] == "3200.00"
    assert record["net_amount"] == "46800.00"
    assert record["currency"] == "INR"
    assert record["published_at"] is None
    assert record["scheduled_days"] == "22.00"
    assert record["payable_days"] == "22.00"
    codes = {line["code"]: line["amount"] for line in record["lines"]}
    assert codes["BASIC"] == "25000.00"
    assert codes["HRA"] == "12500.00"
    assert codes["STD_ALLOW"] == "4167.00"
    assert codes["PERF_BONUS"] == "4165.00"
    assert codes["LTA"] == "4165.00"
    assert codes["FIXED_ALLOW"] == "3.00"
    assert codes["PF"] == "-3000.00"
    assert codes["PT"] == "-200.00"
    assert codes["PF_EMPLOYER"] == "3000.00"

    listed = await client.get("/api/payroll", headers=headers)
    assert listed.status_code == 200
    period = next(row for row in listed.json()["periods"] if row["id"] == period_id)
    assert period["status"] == "FINALIZED"
    listed_record = next(
        row for row in listed.json()["records"] if row["employee_id"] == employee_id and row["id"] == record["id"]
    )
    assert listed_record["net_amount"] == "46800.00"
    assert listed_record["published_at"] is None

    employee_listed = await client.get(
        "/api/payroll",
        headers={"Authorization": f"Bearer {employee['access_token']}"},
    )
    assert employee_listed.status_code == 200
    assert period_id not in {row["id"] for row in employee_listed.json()["periods"]}
    assert record["id"] not in {row["id"] for row in employee_listed.json()["records"]}

    later = await client.patch(
        _salary_url(employee_id),
        headers=headers,
        json={"monthly_wage": "70000.00", "effective_from": "2026-12-01"},
    )
    assert later.status_code == 200
    assert later.json()["monthly_wage"] == "70000.00"

    listed_after = await client.get("/api/payroll", headers=headers)
    still = next(
        row
        for row in listed_after.json()["records"]
        if row["employee_id"] == employee_id and row["id"] == record["id"]
    )
    assert still["net_amount"] == "46800.00"

    again = await client.post(f"/api/payroll/periods/{period_id}/finalize", headers=headers)
    assert again.status_code == 409
    assert again.json()["detail"] == "Only a draft payroll period can be finalized."

    async with SessionLocal() as session:
        stored = await session.get(PayrollRecord, UUID(record["id"]))
        assert stored is not None
        assert stored.net_amount == Decimal("46800.00")
        audit = await session.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "payroll_period",
                AuditEvent.entity_id == period_id,
                AuditEvent.action == "payroll.period.finalize",
            )
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit is not None
        assert audit.after_json is not None
        assert audit.after_json["status"] == "FINALIZED"


async def test_publish_makes_payslips_visible_to_employee(client: AsyncClient):
    period_id = await _draft_period_for_demo()
    employee = await _sign_in(client, "employee@dayflow.demo", PASSWORD)
    employee_id = employee["user"]["employee_id"]
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {hr['access_token']}"}

    employee_forbidden = await client.post(
        f"/api/payroll/periods/{period_id}/publish",
        headers={"Authorization": f"Bearer {employee['access_token']}"},
    )
    assert employee_forbidden.status_code == 403
    assert employee_forbidden.json()["detail"] == "HR role required."

    before_finalize = await client.post(f"/api/payroll/periods/{period_id}/publish", headers=headers)
    assert before_finalize.status_code == 409
    assert before_finalize.json()["detail"] == "A payroll period must be finalized before it is published."

    await _ensure_present_days(employee_id, date(2026, 9, 1), date(2026, 9, 30))
    finalized = await client.post(f"/api/payroll/periods/{period_id}/finalize", headers=headers)
    assert finalized.status_code == 200
    staff_record = next(row for row in finalized.json()["records"] if row["employee_id"] == employee_id)
    record_id = staff_record["id"]

    hidden = await client.get(
        "/api/payroll",
        headers={"Authorization": f"Bearer {employee['access_token']}"},
    )
    assert hidden.status_code == 200
    assert record_id not in {row["id"] for row in hidden.json()["records"]}

    published = await client.post(f"/api/payroll/periods/{period_id}/publish", headers=headers)
    assert published.status_code == 200
    body = published.json()
    assert body["id"] == period_id
    assert body["status"] == "PUBLISHED"
    published_record = next(row for row in body["records"] if row["id"] == record_id)
    assert published_record["employee_id"] == employee_id
    assert published_record["net_amount"] == "46800.00"
    assert published_record["published_at"] is not None

    visible = await client.get(
        "/api/payroll",
        headers={"Authorization": f"Bearer {employee['access_token']}"},
    )
    assert visible.status_code == 200
    assert period_id in {row["id"] for row in visible.json()["periods"]}
    seen = next(row for row in visible.json()["records"] if row["id"] == record_id)
    assert seen["employee_id"] == employee_id
    assert seen["net_amount"] == "46800.00"
    assert seen["published_at"] is not None

    again = await client.post(f"/api/payroll/periods/{period_id}/publish", headers=headers)
    assert again.status_code == 409
    assert again.json()["detail"] == "A payroll period must be finalized before it is published."

    async with SessionLocal() as session:
        audit = await session.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "payroll_period",
                AuditEvent.entity_id == period_id,
                AuditEvent.action == "payroll.period.publish",
            )
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit is not None
        assert audit.after_json is not None
        assert audit.after_json["status"] == "PUBLISHED"


async def test_hr_dashboard_payload_uses_real_org_counts(client: AsyncClient):
    suffix = uuid4().hex[:8]
    email = f"hr.dash.{suffix}@dayflow.demo"

    async with SessionLocal() as session:
        org = Organization(name=f"Dash Co {suffix}", timezone="Asia/Kolkata", currency="INR")
        session.add(org)
        await session.flush()
        hr_user = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            email_verified_at=datetime.now(UTC),
            status=UserStatus.ACTIVE.value,
        )
        session.add(hr_user)
        await session.flush()
        session.add(
            OrganizationMembership(organization_id=org.id, user_id=hr_user.id, role=Role.HR.value)
        )
        people: list[Employee] = []
        for index, code in enumerate(("D-001", "D-002", "D-003"), start=1):
            person = Employee(
                organization_id=org.id,
                user_id=hr_user.id if index == 1 else None,
                employee_code=code,
                first_name="Dash",
                last_name=f"{index}",
                status=EmployeeStatus.ACTIVE.value,
                joined_on=date(2026, 1, 1),
            )
            session.add(person)
            people.append(person)
        await session.flush()
        paid = LeaveType(
            organization_id=org.id,
            name="Paid leave",
            code="PAID",
            is_paid=True,
            requires_balance=True,
        )
        session.add(paid)
        await session.flush()
        session.add_all(
            [
                LeaveRequest(
                    employee_id=people[1].id,
                    leave_type_id=paid.id,
                    starts_on=date(2026, 9, 1),
                    ends_on=date(2026, 9, 2),
                    counted_days=2,
                    reason="Pending one",
                    status="PENDING",
                    submitted_at=datetime.now(UTC),
                ),
                LeaveRequest(
                    employee_id=people[2].id,
                    leave_type_id=paid.id,
                    starts_on=date(2026, 9, 8),
                    ends_on=date(2026, 9, 9),
                    counted_days=2,
                    reason="Pending two",
                    status="PENDING",
                    submitted_at=datetime.now(UTC),
                ),
                AttendanceSession(
                    employee_id=people[1].id,
                    work_date=date(2026, 8, 21),
                    check_in_at=datetime(2026, 8, 21, 4, 0, tzinfo=UTC),
                    source="SERVER",
                    status="OPEN",
                ),
                PayrollPeriod(
                    organization_id=org.id,
                    starts_on=date(2026, 7, 1),
                    ends_on=date(2026, 7, 31),
                    pay_date=date(2026, 8, 5),
                    status=PayrollPeriodStatus.DRAFT.value,
                ),
            ]
        )
        await session.commit()

    session_body = await _sign_in(client, email, PASSWORD)
    headers = {"Authorization": f"Bearer {session_body['access_token']}"}
    response = await client.get("/api/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "HR"
    assert body["headline"] == "Today's coverage"
    assert body["headcount"] == 3
    assert body["pending_approvals"] == 2
    assert body["attendance_exceptions"] == 1
    assert body["payroll_period_due"] is True


async def test_employee_dashboard_payload_uses_real_attendance_and_balances(client: AsyncClient):
    suffix = uuid4().hex[:8]
    email = f"emp.dash.{suffix}@dayflow.demo"

    async with SessionLocal() as session:
        org = Organization(name=f"Emp Dash {suffix}", timezone="Asia/Kolkata", currency="INR")
        session.add(org)
        await session.flush()
        user = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            email_verified_at=datetime.now(UTC),
            status=UserStatus.ACTIVE.value,
        )
        session.add(user)
        await session.flush()
        session.add(
            OrganizationMembership(organization_id=org.id, user_id=user.id, role=Role.EMPLOYEE.value)
        )
        employee = Employee(
            organization_id=org.id,
            user_id=user.id,
            employee_code=f"ED-{suffix[:4].upper()}",
            first_name="Emp",
            last_name="Dash",
            status=EmployeeStatus.ACTIVE.value,
            joined_on=date(2026, 1, 1),
        )
        session.add(employee)
        await session.flush()
        paid = LeaveType(
            organization_id=org.id,
            name="Paid leave",
            code="PAID",
            is_paid=True,
            requires_balance=True,
        )
        session.add(paid)
        await session.flush()
        session.add(
            LeaveBalance(
                employee_id=employee.id,
                leave_type_id=paid.id,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 12, 31),
                granted_days=12,
            )
        )
        session.add(
            PayrollPeriod(
                organization_id=org.id,
                starts_on=date(2026, 8, 1),
                ends_on=date(2026, 8, 31),
                pay_date=date(2026, 9, 5),
                status=PayrollPeriodStatus.PUBLISHED.value,
                published_at=datetime(2026, 9, 1, tzinfo=UTC),
            )
        )
        await session.commit()

    session_body = await _sign_in(client, email, PASSWORD)
    headers = {"Authorization": f"Bearer {session_body['access_token']}"}
    response = await client.get("/api/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "EMPLOYEE"
    assert body["headline"] == "Check in when the workday starts"
    assert body["attendance_state"] == "not_checked_in"
    assert body["leave_balances"] == [{"leave_type": "PAID", "remaining_days": 12}]
    assert body["next_pay_date"] == "2026-09-05"
    assert body["incomplete_profile"] is True

    checked_in = await client.post("/api/attendance/check-in", headers=headers)
    assert checked_in.status_code == 200
    after = await client.get("/api/dashboard", headers=headers)
    assert after.status_code == 200
    assert after.json()["attendance_state"] == "checked_in"
    assert after.json()["headline"] == "You are checked in"


async def test_payroll_mutations_are_organization_scoped(client: AsyncClient):
    suffix = uuid4().hex[:8]
    foreign_period_id = None
    foreign_employee_id = None

    async with SessionLocal() as session:
        other_org = Organization(name=f"Pay Scope {suffix}", timezone="Asia/Kolkata", currency="INR")
        session.add(other_org)
        await session.flush()
        other_user = User(
            email=f"scope.{suffix}@dayflow.demo",
            password_hash=hash_password(PASSWORD),
            email_verified_at=datetime.now(UTC),
            status=UserStatus.ACTIVE.value,
        )
        session.add(other_user)
        await session.flush()
        foreign_employee = Employee(
            organization_id=other_org.id,
            user_id=other_user.id,
            employee_code=f"SC-{suffix[:4].upper()}",
            first_name="Scope",
            last_name="Pay",
            status=EmployeeStatus.ACTIVE.value,
            joined_on=date(2026, 1, 1),
        )
        session.add(foreign_employee)
        await session.flush()
        foreign_period = PayrollPeriod(
            organization_id=other_org.id,
            starts_on=date(2026, 9, 1),
            ends_on=date(2026, 9, 30),
            pay_date=date(2026, 10, 5),
            status=PayrollPeriodStatus.DRAFT.value,
        )
        session.add(foreign_period)
        await session.commit()
        foreign_period_id = str(foreign_period.id)
        foreign_employee_id = str(foreign_employee.id)

    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {hr['access_token']}"}
    patched = await client.patch(
        _salary_url(foreign_employee_id),
        headers=headers,
        json={"monthly_wage": "1.00"},
    )
    assert patched.status_code == 404
    assert patched.json()["detail"] == "Employee not found."

    finalize = await client.post(f"/api/payroll/periods/{foreign_period_id}/finalize", headers=headers)
    assert finalize.status_code == 404
    assert finalize.json()["detail"] == "Payroll period not found."

    publish = await client.post(f"/api/payroll/periods/{foreign_period_id}/publish", headers=headers)
    assert publish.status_code == 404
    assert publish.json()["detail"] == "Payroll period not found."


async def _isolated_payroll_org(suffix: str) -> tuple[str, str, str, str]:
    email = f"hr.paydays.{suffix}@dayflow.demo"
    async with SessionLocal() as session:
        org = Organization(name=f"Pay Days {suffix}", timezone="Asia/Kolkata", currency="INR")
        session.add(org)
        await session.flush()
        session.add(WorkPolicy(organization_id=org.id))
        hr_user = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            email_verified_at=datetime.now(UTC),
            status=UserStatus.ACTIVE.value,
        )
        session.add(hr_user)
        await session.flush()
        session.add(OrganizationMembership(organization_id=org.id, user_id=hr_user.id, role=Role.HR.value))
        employee = Employee(
            organization_id=org.id,
            user_id=hr_user.id,
            employee_code=f"PD-{suffix[:4].upper()}",
            first_name="Pay",
            last_name="Days",
            status=EmployeeStatus.ACTIVE.value,
            joined_on=date(2026, 1, 1),
        )
        session.add(employee)
        await session.flush()
        await assign_default_salary(
            session,
            organization_id=org.id,
            employee_id=employee.id,
            effective_from=date(2026, 1, 1),
        )
        period = PayrollPeriod(
            organization_id=org.id,
            starts_on=date(2026, 9, 1),
            ends_on=date(2026, 9, 4),
            pay_date=date(2026, 9, 5),
            status=PayrollPeriodStatus.DRAFT.value,
        )
        session.add(period)
        await session.commit()
        return email, PASSWORD, str(employee.id), str(period.id)


async def test_finalize_blocked_by_open_session_in_period(client: AsyncClient):
    suffix = uuid4().hex[:8]
    email, password, employee_id, period_id = await _isolated_payroll_org(suffix)
    async with SessionLocal() as session:
        session.add(
            AttendanceSession(
                employee_id=employee_id,
                work_date=date(2026, 9, 1),
                check_in_at=datetime(2026, 9, 1, 3, 30, tzinfo=UTC),
                source="SERVER",
                status="OPEN",
            )
        )
        await session.commit()

    hr = await _sign_in(client, email, password)
    headers = {"Authorization": f"Bearer {hr['access_token']}"}
    blocked = await client.post(f"/api/payroll/periods/{period_id}/finalize", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "Open attendance sessions in this period block finalization."


async def test_finalize_prorates_by_payable_days_and_snapshots_counts(client: AsyncClient):
    from app.domain.payroll import compute_salary, default_salary_structure, prorate_computed_salary

    suffix = uuid4().hex[:8]
    email, password, employee_id, period_id = await _isolated_payroll_org(suffix)
    async with SessionLocal() as session:
        unpaid = LeaveType(
            organization_id=(await session.get(Employee, employee_id)).organization_id,
            name="Unpaid leave",
            code="UNPAID",
            is_paid=False,
            requires_balance=False,
        )
        session.add(unpaid)
        await session.flush()
        session.add_all(
            [
                AttendanceSession(
                    employee_id=employee_id,
                    work_date=date(2026, 9, 1),
                    check_in_at=datetime(2026, 9, 1, 3, 30, tzinfo=UTC),
                    check_out_at=datetime(2026, 9, 1, 12, 30, tzinfo=UTC),
                    source="SERVER",
                    status="PRESENT",
                    worked_minutes=540,
                ),
                AttendanceSession(
                    employee_id=employee_id,
                    work_date=date(2026, 9, 2),
                    check_in_at=datetime(2026, 9, 2, 3, 30, tzinfo=UTC),
                    check_out_at=datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
                    source="SERVER",
                    status="HALF_DAY",
                    worked_minutes=270,
                ),
                LeaveRequest(
                    employee_id=employee_id,
                    leave_type_id=unpaid.id,
                    starts_on=date(2026, 9, 3),
                    ends_on=date(2026, 9, 3),
                    counted_days=1,
                    reason="Unpaid day",
                    status="APPROVED",
                    submitted_at=datetime.now(UTC),
                ),
            ]
        )
        await session.commit()

    hr = await _sign_in(client, email, password)
    headers = {"Authorization": f"Bearer {hr['access_token']}"}
    finalized = await client.post(f"/api/payroll/periods/{period_id}/finalize", headers=headers)
    assert finalized.status_code == 200
    record = next(row for row in finalized.json()["records"] if row["employee_id"] == employee_id)
    assert record["scheduled_days"] == "4.00"
    assert record["payable_days"] == "1.50"
    expected = prorate_computed_salary(
        compute_salary(Decimal("50000.00"), default_salary_structure()),
        payable_days=Decimal("1.5"),
        scheduled_days=Decimal("4"),
    )
    assert record["gross_amount"] == f"{expected.gross_amount:.2f}"
    assert record["net_amount"] == f"{expected.net_amount:.2f}"
    assert record["net_amount"] != "46800.00"
    codes = {line["code"]: line["amount"] for line in record["lines"]}
    assert codes["PT"] == "-200.00"
    assert Decimal(codes["PF"].lstrip("-")) == Decimal(codes["BASIC"]) * Decimal("0.12")

    published = await client.post(f"/api/payroll/periods/{period_id}/publish", headers=headers)
    assert published.status_code == 200
    published_record = next(row for row in published.json()["records"] if row["id"] == record["id"])
    assert published_record["payable_days"] == "1.50"
    assert published_record["scheduled_days"] == "4.00"
    assert published_record["net_amount"] == record["net_amount"]
