from datetime import date
from uuid import uuid4

from httpx import AsyncClient

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.domain.roles import EmployeeStatus, Role, UserStatus
from app.models import Employee, JobAssignment, Organization, OrganizationMembership, User


async def _sign_in(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post(
        "/api/auth/sign-in",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


async def test_hr_lists_organization_employees(client: AsyncClient):
    session = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    token = session["access_token"]

    response = await client.get(
        "/api/employees",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    people = response.json()
    assert isinstance(people, list)
    codes = {person["employee_code"] for person in people}
    assert "HR-001" in codes
    assert "EMP-014" in codes
    for person in people:
        assert "id" in person
        assert "first_name" in person
        assert "last_name" in person
        assert "status" in person


async def test_employee_can_list_directory(client: AsyncClient):
    session = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    token = session["access_token"]

    response = await client.get(
        "/api/employees",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    people = response.json()
    codes = {person["employee_code"] for person in people}
    assert "HR-001" in codes
    assert "EMP-014" in codes
    hr_row = next(person for person in people if person["employee_code"] == "HR-001")
    assert hr_row["email"] == "hr@dayflow.demo"
    assert hr_row["role"] == "HR"


async def test_employee_can_get_own_record(client: AsyncClient):
    session = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    token = session["access_token"]
    employee_id = session["user"]["employee_id"]

    response = await client.get(
        f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    person = response.json()
    assert person["id"] == employee_id
    assert person["employee_code"] == "EMP-014"
    assert person["first_name"] == "Rohan"
    assert person["last_name"] == "Iyer"
    assert "phone" in person
    assert "address" in person


async def test_employee_can_get_a_peer_record(client: AsyncClient):
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    other_id = hr["user"]["employee_id"]

    employee = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    token = employee["access_token"]

    response = await client.get(
        f"/api/employees/{other_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    person = response.json()
    assert person["id"] == other_id
    assert person["employee_code"] == "HR-001"
    assert person["email"] == "hr@dayflow.demo"
    assert person["role"] == "HR"


async def test_employee_get_guessed_uuid_returns_404(client: AsyncClient):
    employee = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    token = employee["access_token"]
    guessed = uuid4()

    response = await client.get(
        f"/api/employees/{guessed}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Employee not found."


async def test_employee_can_patch_own_address_and_phone(client: AsyncClient):
    session = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    token = session["access_token"]
    employee_id = session["user"]["employee_id"]

    response = await client.patch(
        f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"phone": "+91-90000-11114", "address": "Mysuru"},
    )
    assert response.status_code == 200
    person = response.json()
    assert person["phone"] == "+91-90000-11114"
    assert person["address"] == "Mysuru"
    assert person["employee_code"] == "EMP-014"

    again = await client.get(
        f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 200
    assert again.json()["phone"] == "+91-90000-11114"
    assert again.json()["address"] == "Mysuru"


async def test_employee_cannot_patch_job_fields(client: AsyncClient):
    session = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    token = session["access_token"]
    employee_id = session["user"]["employee_id"]

    response = await client.patch(
        f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "CTO", "department": "Executive"},
    )
    assert response.status_code == 403
    assert "title" in response.json()["detail"]
    assert "department" in response.json()["detail"]


async def test_hr_can_patch_job_fields(client: AsyncClient):
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    employee = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    employee_id = employee["user"]["employee_id"]
    token = hr["access_token"]

    response = await client.patch(
        f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Senior Operations Associate",
            "department": "Operations",
            "employment_type": "FULL_TIME",
            "location": "Hyderabad",
            "first_name": "Rohan",
            "status": "ACTIVE",
        },
    )
    assert response.status_code == 200
    person = response.json()
    assert person["title"] == "Senior Operations Associate"
    assert person["department"] == "Operations"
    assert person["employment_type"] == "FULL_TIME"
    assert person["location"] == "Hyderabad"
    assert person["first_name"] == "Rohan"
    assert person["status"] == "ACTIVE"


async def test_employee_queries_are_organization_scoped(client: AsyncClient):
    suffix = uuid4().hex[:8]
    other_email = f"hr.other.{suffix}@dayflow.demo"
    other_password = "ChangeMe_Other12!"
    other_employee_id = None

    async with SessionLocal() as session:
        other_org = Organization(name=f"Other Co {suffix}", timezone="Asia/Kolkata", currency="INR")
        session.add(other_org)
        await session.flush()

        other_hr = User(
            email=other_email,
            password_hash=hash_password(other_password),
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
        foreign = Employee(
            organization_id=other_org.id,
            user_id=other_hr.id,
            employee_code=f"XR-{suffix[:4].upper()}",
            first_name="Foreign",
            last_name="Worker",
            status=EmployeeStatus.ACTIVE.value,
            joined_on=date(2025, 1, 1),
        )
        session.add(foreign)
        await session.flush()
        session.add(
            JobAssignment(
                employee_id=foreign.id,
                title="Analyst",
                department="Finance",
                employment_type="FULL_TIME",
                location="Pune",
                starts_on=date(2025, 1, 1),
            )
        )
        other_employee_id = str(foreign.id)
        await session.commit()

    demo_hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    token = demo_hr["access_token"]

    listed = await client.get(
        "/api/employees",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    codes = {person["employee_code"] for person in listed.json()}
    assert f"XR-{suffix[:4].upper()}" not in codes
    assert other_employee_id not in {person["id"] for person in listed.json()}

    foreign_get = await client.get(
        f"/api/employees/{other_employee_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert foreign_get.status_code == 404
    assert foreign_get.json()["detail"] == "Employee not found."

    foreign_patch = await client.patch(
        f"/api/employees/{other_employee_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"phone": "+91-00000-00000"},
    )
    assert foreign_patch.status_code == 404
    assert foreign_patch.json()["detail"] == "Employee not found."


async def test_employee_cannot_patch_another_employee(client: AsyncClient):
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    other_id = hr["user"]["employee_id"]
    employee = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    token = employee["access_token"]

    response = await client.patch(
        f"/api/employees/{other_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"phone": "+91-90000-99999"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Employees can edit only their own record."


async def test_employee_patch_writes_audit_event(client: AsyncClient):
    from sqlalchemy import select

    from app.models import AuditEvent

    session = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    token = session["access_token"]
    employee_id = session["user"]["employee_id"]
    phone = f"+91-90000-{uuid4().hex[:5]}"

    response = await client.patch(
        f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"phone": phone},
    )
    assert response.status_code == 200
    assert response.json()["phone"] == phone

    async with SessionLocal() as db:
        event = await db.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "employee",
                AuditEvent.entity_id == employee_id,
                AuditEvent.action == "employee.update",
            )
            .order_by(AuditEvent.created_at.desc())
        )
        assert event is not None
        assert event.after_json is not None
        assert event.after_json["phone"] == phone
        assert event.actor_user_id is not None


async def test_hr_inactive_status_disables_sign_in(client: AsyncClient):
    employee = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    employee_id = employee["user"]["employee_id"]
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")

    patched = await client.patch(
        f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {hr['access_token']}"},
        json={"status": "INACTIVE"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "INACTIVE"

    locked = await client.post(
        "/api/auth/sign-in",
        json={"email": "employee@dayflow.demo", "password": "ChangeMe_Emp12!"},
    )
    assert locked.status_code == 403
    assert locked.json()["detail"] == "Account is locked or disabled."

    restored = await client.patch(
        f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {hr['access_token']}"},
        json={"status": "ACTIVE"},
    )
    assert restored.status_code == 200
    again = await client.post(
        "/api/auth/sign-in",
        json={"email": "employee@dayflow.demo", "password": "ChangeMe_Emp12!"},
    )
    assert again.status_code == 200


async def test_patch_rejects_null_required_fields(client: AsyncClient):
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    employee = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    employee_id = employee["user"]["employee_id"]

    response = await client.patch(
        f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {hr['access_token']}"},
        json={"first_name": None, "title": None},
    )
    assert response.status_code == 400
    assert "cannot be empty" in response.json()["detail"]
