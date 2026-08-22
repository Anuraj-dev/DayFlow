from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.domain.payroll import PayrollPeriodStatus
from app.domain.roles import EmployeeStatus, Role, UserStatus
from app.models import (
    AttendanceSession,
    AuditEvent,
    Employee,
    EmployeeSalaryComponent,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    Organization,
    OrganizationMembership,
    PayrollPeriod,
    PayrollRecord,
    SalaryComponent,
    User,
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
        assert row["net_amount"] == "51200.00"
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


async def test_hr_patches_salary_components_while_period_is_draft(client: AsyncClient):
    period_id = await _draft_period_for_demo()
    employee = await _sign_in(client, "employee@dayflow.demo", PASSWORD)
    employee_id = employee["user"]["employee_id"]
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {hr['access_token']}"}

    patched = await client.patch(
        "/api/payroll/salary-components",
        headers=headers,
        json={
            "employee_id": employee_id,
            "period_id": period_id,
            "components": [{"code": "BASIC", "amount": "42000.00"}],
        },
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["employee_id"] == employee_id
    basic = next(row for row in body["components"] if row["code"] == "BASIC")
    assert basic["amount"] == "42000.00"
    assert basic["kind"] == "EARNING"

    async with SessionLocal() as session:
        stored = await session.scalar(
            select(EmployeeSalaryComponent)
            .join(SalaryComponent, SalaryComponent.id == EmployeeSalaryComponent.salary_component_id)
            .where(
                EmployeeSalaryComponent.employee_id == UUID(employee_id),
                SalaryComponent.code == "BASIC",
            )
        )
        assert stored is not None
        assert stored.amount == Decimal("42000.00")
        audit = await session.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "employee_salary_component",
                AuditEvent.action == "payroll.salary.update",
                AuditEvent.entity_id == str(stored.id),
            )
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit is not None
        assert audit.after_json is not None
        assert audit.after_json["amount"] == "42000.00"
        assert audit.after_json["code"] == "BASIC"


async def test_employee_cannot_patch_salary_components(client: AsyncClient):
    period_id = await _draft_period_for_demo()
    employee = await _sign_in(client, "employee@dayflow.demo", PASSWORD)
    headers = {"Authorization": f"Bearer {employee['access_token']}"}
    patched = await client.patch(
        "/api/payroll/salary-components",
        headers=headers,
        json={
            "employee_id": employee["user"]["employee_id"],
            "period_id": period_id,
            "components": [{"code": "BASIC", "amount": "1.00"}],
        },
    )
    assert patched.status_code == 403
    assert patched.json()["detail"] == "HR role required."


async def test_mutating_finalized_period_returns_409(client: AsyncClient):
    async with SessionLocal() as session:
        org = await session.scalar(_select_org())
        assert org is not None
        published = await session.scalar(
            select(PayrollPeriod).where(
                PayrollPeriod.organization_id == org.id,
                PayrollPeriod.status == PayrollPeriodStatus.PUBLISHED.value,
            )
        )
        assert published is not None
        period_id = str(published.id)

    employee = await _sign_in(client, "employee@dayflow.demo", PASSWORD)
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {hr['access_token']}"}
    patched = await client.patch(
        "/api/payroll/salary-components",
        headers=headers,
        json={
            "employee_id": employee["user"]["employee_id"],
            "period_id": period_id,
            "components": [{"code": "BASIC", "amount": "43000.00"}],
        },
    )
    assert patched.status_code == 409
    assert patched.json()["detail"] == "Finalized payroll records are immutable."


async def test_hr_finalize_snapshots_salary_and_locks_period(client: AsyncClient):
    period_id = await _draft_period_for_demo()
    employee = await _sign_in(client, "employee@dayflow.demo", PASSWORD)
    employee_id = employee["user"]["employee_id"]
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {hr['access_token']}"}

    patched = await client.patch(
        "/api/payroll/salary-components",
        headers=headers,
        json={
            "employee_id": employee_id,
            "period_id": period_id,
            "components": [
                {"code": "BASIC", "amount": "41000.00"},
                {"code": "HRA", "amount": "16000.00"},
                {"code": "PF", "amount": "4800.00"},
            ],
        },
    )
    assert patched.status_code == 200

    finalized = await client.post(f"/api/payroll/periods/{period_id}/finalize", headers=headers)
    assert finalized.status_code == 200
    body = finalized.json()
    assert body["id"] == period_id
    assert body["status"] == "FINALIZED"
    assert body["starts_on"] == "2026-09-01"
    assert body["ends_on"] == "2026-09-30"
    assert body["pay_date"] == "2026-10-05"
    records = body["records"]
    assert len(records) == 1
    assert records[0]["employee_id"] == employee_id
    assert records[0]["gross_amount"] == "57000.00"
    assert records[0]["deduction_amount"] == "4800.00"
    assert records[0]["net_amount"] == "52200.00"
    assert records[0]["currency"] == "INR"
    assert records[0]["published_at"] is None
    codes = {line["code"]: line["amount"] for line in records[0]["lines"]}
    assert codes["BASIC"] == "41000.00"
    assert codes["HRA"] == "16000.00"
    assert codes["PF"] == "-4800.00"

    listed = await client.get("/api/payroll", headers=headers)
    assert listed.status_code == 200
    period = next(row for row in listed.json()["periods"] if row["id"] == period_id)
    assert period["status"] == "FINALIZED"
    record = next(row for row in listed.json()["records"] if row["employee_id"] == employee_id and row["id"] == records[0]["id"])
    assert record["net_amount"] == "52200.00"
    assert record["published_at"] is None

    employee_listed = await client.get(
        "/api/payroll",
        headers={"Authorization": f"Bearer {employee['access_token']}"},
    )
    assert employee_listed.status_code == 200
    assert period_id not in {row["id"] for row in employee_listed.json()["periods"]}
    assert records[0]["id"] not in {row["id"] for row in employee_listed.json()["records"]}

    locked = await client.patch(
        "/api/payroll/salary-components",
        headers=headers,
        json={
            "employee_id": employee_id,
            "period_id": period_id,
            "components": [{"code": "BASIC", "amount": "1.00"}],
        },
    )
    assert locked.status_code == 409
    assert locked.json()["detail"] == "Finalized payroll records are immutable."

    again = await client.post(f"/api/payroll/periods/{period_id}/finalize", headers=headers)
    assert again.status_code == 409
    assert again.json()["detail"] == "Only a draft payroll period can be finalized."

    async with SessionLocal() as session:
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
        assert audit.after_json["net_amount"] == "52200.00"


async def test_publish_makes_payslips_visible_to_employee(client: AsyncClient):
    period_id = await _draft_period_for_demo()
    employee = await _sign_in(client, "employee@dayflow.demo", PASSWORD)
    employee_id = employee["user"]["employee_id"]
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {hr['access_token']}"}

    patched = await client.patch(
        "/api/payroll/salary-components",
        headers=headers,
        json={
            "employee_id": employee_id,
            "period_id": period_id,
            "components": [
                {"code": "BASIC", "amount": "40000.00"},
                {"code": "HRA", "amount": "16000.00"},
                {"code": "PF", "amount": "4800.00"},
            ],
        },
    )
    assert patched.status_code == 200

    employee_forbidden = await client.post(
        f"/api/payroll/periods/{period_id}/publish",
        headers={"Authorization": f"Bearer {employee['access_token']}"},
    )
    assert employee_forbidden.status_code == 403
    assert employee_forbidden.json()["detail"] == "HR role required."

    before_finalize = await client.post(f"/api/payroll/periods/{period_id}/publish", headers=headers)
    assert before_finalize.status_code == 409
    assert before_finalize.json()["detail"] == "A payroll period must be finalized before it is published."

    finalized = await client.post(f"/api/payroll/periods/{period_id}/finalize", headers=headers)
    assert finalized.status_code == 200
    record_id = finalized.json()["records"][0]["id"]

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
    assert body["records"][0]["id"] == record_id
    assert body["records"][0]["employee_id"] == employee_id
    assert body["records"][0]["net_amount"] == "51200.00"
    assert body["records"][0]["published_at"] is not None

    visible = await client.get(
        "/api/payroll",
        headers={"Authorization": f"Bearer {employee['access_token']}"},
    )
    assert visible.status_code == 200
    assert period_id in {row["id"] for row in visible.json()["periods"]}
    seen = next(row for row in visible.json()["records"] if row["id"] == record_id)
    assert seen["employee_id"] == employee_id
    assert seen["net_amount"] == "51200.00"
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
        "/api/payroll/salary-components",
        headers=headers,
        json={
            "employee_id": foreign_employee_id,
            "period_id": foreign_period_id,
            "components": [{"code": "BASIC", "amount": "1.00"}],
        },
    )
    assert patched.status_code == 404
    assert patched.json()["detail"] == "Payroll period not found."

    finalize = await client.post(f"/api/payroll/periods/{foreign_period_id}/finalize", headers=headers)
    assert finalize.status_code == 404
    assert finalize.json()["detail"] == "Payroll period not found."

    publish = await client.post(f"/api/payroll/periods/{foreign_period_id}/publish", headers=headers)
    assert publish.status_code == 404
    assert publish.json()["detail"] == "Payroll period not found."
