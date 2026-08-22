import hashlib
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.domain.roles import EmployeeStatus, Role, UserStatus
from app.models import AccountInvite, Employee, Organization, OrganizationMembership, User

settings = get_settings()


def _invite_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def test_seeded_hr_can_sign_in_and_reach_me(client: AsyncClient):
    response = await client.post(
        "/api/auth/sign-in",
        json={"email": "hr@dayflow.demo", "password": "ChangeMe_HR12!"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    user = payload["user"]
    assert user["email"] == "hr@dayflow.demo"
    assert user["role"] == "HR"
    assert user["first_name"] == "Asha"
    assert user["last_name"] == "Mehta"
    assert user["employee_code"] == "HR-001"
    assert user["employee_id"] is not None

    me = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "hr@dayflow.demo"
    assert me.json()["role"] == "HR"
    assert me.json()["employee_code"] == "HR-001"
    assert me.json()["id"] == user["id"]
    assert me.json()["organization_id"] == user["organization_id"]
    assert me.json()["employee_id"] == user["employee_id"]


async def test_seeded_employee_can_sign_in_and_reach_me(client: AsyncClient):
    response = await client.post(
        "/api/auth/sign-in",
        json={"email": "employee@dayflow.demo", "password": "ChangeMe_Emp12!"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    user = payload["user"]
    assert user["email"] == "employee@dayflow.demo"
    assert user["role"] == "EMPLOYEE"
    assert user["first_name"] == "Rohan"
    assert user["last_name"] == "Iyer"
    assert user["employee_code"] == "EMP-014"
    assert user["employee_id"] is not None

    me = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "employee@dayflow.demo"
    assert me.json()["role"] == "EMPLOYEE"
    assert me.json()["employee_code"] == "EMP-014"
    assert me.json()["id"] == user["id"]
    assert me.json()["organization_id"] == user["organization_id"]
    assert me.json()["employee_id"] == user["employee_id"]


async def test_sign_in_rejects_bad_credentials_with_401(client: AsyncClient):
    response = await client.post(
        "/api/auth/sign-in",
        json={"email": "hr@dayflow.demo", "password": "WrongPassword1!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Bad credentials."


async def test_sign_in_rejects_disabled_account_with_403(client: AsyncClient):
    suffix = uuid4().hex[:8]
    email = f"locked.{suffix}@dayflow.demo"
    password = "ChangeMe_Lock12!"
    async with SessionLocal() as session:
        org = await session.scalar(select(Organization).limit(1))
        assert org is not None
        user = User(
            email=email,
            password_hash=hash_password(password),
            status=UserStatus.DISABLED.value,
        )
        session.add(user)
        await session.flush()
        session.add(
            OrganizationMembership(
                organization_id=org.id, user_id=user.id, role=Role.EMPLOYEE.value
            )
        )
        session.add(
            Employee(
                organization_id=org.id,
                user_id=user.id,
                employee_code=f"DIS-{suffix}",
                first_name="Locked",
                last_name="Account",
                status=EmployeeStatus.INACTIVE.value,
                joined_on=date(2026, 1, 1),
            )
        )
        await session.commit()

    response = await client.post(
        "/api/auth/sign-in",
        json={"email": email, "password": password},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Account is locked or disabled."


async def test_activate_account_accepts_valid_unused_invite(client: AsyncClient):
    suffix = uuid4().hex[:8]
    email = f"new.hire.{suffix}@dayflow.demo"
    employee_code = f"EMP-{suffix[:4].upper()}"
    token = "invite-token-1"
    password = "ChangeMe_Emp12!"

    async with SessionLocal() as session:
        org = await session.scalar(select(Organization).limit(1))
        hr = await session.scalar(select(User).where(User.email == "hr@dayflow.demo"))
        assert org is not None and hr is not None
        employee = Employee(
            organization_id=org.id,
            employee_code=employee_code,
            first_name="New",
            last_name="Hire",
            status=EmployeeStatus.INVITED.value,
            joined_on=date(2026, 8, 1),
        )
        session.add(employee)
        await session.flush()
        session.add(
            AccountInvite(
                organization_id=org.id,
                employee_id=employee.id,
                email=email,
                role=Role.EMPLOYEE.value,
                token_hash=_invite_token_hash(token),
                expires_at=datetime.now(UTC) + timedelta(days=7),
                created_by=hr.id,
            )
        )
        await session.commit()

    response = await client.post(
        "/api/auth/activate-account",
        json={
            "employee_code": employee_code,
            "email": email,
            "token": token,
            "password": password,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "verification_sent"
    assert response.json()["detail"] == "Check your work email to verify this account."

    signed_in = await client.post(
        "/api/auth/sign-in",
        json={"email": email, "password": password},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["user"]["role"] == "EMPLOYEE"
    assert signed_in.json()["user"]["email"] == email
    assert signed_in.json()["user"]["employee_code"] == employee_code
    assert signed_in.json()["user"]["first_name"] == "New"
    assert signed_in.json()["user"]["last_name"] == "Hire"


async def test_activate_account_rejects_expired_invite(client: AsyncClient):
    suffix = uuid4().hex[:8]
    email = f"expired.{suffix}@dayflow.demo"
    employee_code = f"EXP-{suffix[:4].upper()}"
    token = "expired-invite-token"
    password = "ChangeMe_Emp12!"

    async with SessionLocal() as session:
        org = await session.scalar(select(Organization).limit(1))
        hr = await session.scalar(select(User).where(User.email == "hr@dayflow.demo"))
        assert org is not None and hr is not None
        employee = Employee(
            organization_id=org.id,
            employee_code=employee_code,
            first_name="Expired",
            last_name="Invite",
            status=EmployeeStatus.INVITED.value,
            joined_on=date(2026, 8, 1),
        )
        session.add(employee)
        await session.flush()
        session.add(
            AccountInvite(
                organization_id=org.id,
                employee_id=employee.id,
                email=email,
                role=Role.EMPLOYEE.value,
                token_hash=_invite_token_hash(token),
                expires_at=datetime.now(UTC) - timedelta(days=1),
                created_by=hr.id,
            )
        )
        await session.commit()

    response = await client.post(
        "/api/auth/activate-account",
        json={
            "employee_code": employee_code,
            "email": email,
            "token": token,
            "password": password,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "This invite has expired."


async def test_activate_account_rejects_already_used_invite(client: AsyncClient):
    suffix = uuid4().hex[:8]
    email = f"used.{suffix}@dayflow.demo"
    employee_code = f"USD-{suffix[:4].upper()}"
    token = "used-invite-token"
    password = "ChangeMe_Emp12!"

    async with SessionLocal() as session:
        org = await session.scalar(select(Organization).limit(1))
        hr = await session.scalar(select(User).where(User.email == "hr@dayflow.demo"))
        assert org is not None and hr is not None
        employee = Employee(
            organization_id=org.id,
            employee_code=employee_code,
            first_name="Used",
            last_name="Invite",
            status=EmployeeStatus.INVITED.value,
            joined_on=date(2026, 8, 1),
        )
        session.add(employee)
        await session.flush()
        session.add(
            AccountInvite(
                organization_id=org.id,
                employee_id=employee.id,
                email=email,
                role=Role.EMPLOYEE.value,
                token_hash=_invite_token_hash(token),
                expires_at=datetime.now(UTC) + timedelta(days=7),
                created_by=hr.id,
            )
        )
        await session.commit()

    first = await client.post(
        "/api/auth/activate-account",
        json={
            "employee_code": employee_code,
            "email": email,
            "token": token,
            "password": password,
        },
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/auth/activate-account",
        json={
            "employee_code": employee_code,
            "email": email,
            "token": token,
            "password": password,
        },
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "This invite has already been used."


async def test_activate_account_never_assigns_hr_from_public_body(client: AsyncClient):
    suffix = uuid4().hex[:8]
    email = f"nohr.{suffix}@dayflow.demo"
    employee_code = f"NHR-{suffix[:4].upper()}"
    token = "employee-invite-token"
    password = "ChangeMe_Emp12!"

    async with SessionLocal() as session:
        org = await session.scalar(select(Organization).limit(1))
        hr = await session.scalar(select(User).where(User.email == "hr@dayflow.demo"))
        assert org is not None and hr is not None
        employee = Employee(
            organization_id=org.id,
            employee_code=employee_code,
            first_name="Public",
            last_name="Body",
            status=EmployeeStatus.INVITED.value,
            joined_on=date(2026, 8, 1),
        )
        session.add(employee)
        await session.flush()
        session.add(
            AccountInvite(
                organization_id=org.id,
                employee_id=employee.id,
                email=email,
                role=Role.EMPLOYEE.value,
                token_hash=_invite_token_hash(token),
                expires_at=datetime.now(UTC) + timedelta(days=7),
                created_by=hr.id,
            )
        )
        await session.commit()

    response = await client.post(
        "/api/auth/activate-account",
        json={
            "employee_code": employee_code,
            "email": email,
            "token": token,
            "password": password,
            "role": "HR",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "verification_sent"

    signed_in = await client.post(
        "/api/auth/sign-in",
        json={"email": email, "password": password},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["user"]["role"] == "EMPLOYEE"
    assert signed_in.json()["user"]["email"] == email


async def test_me_requires_authorization(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


async def test_sign_in_unknown_email_is_401(client: AsyncClient):
    response = await client.post(
        "/api/auth/sign-in",
        json={"email": "nobody@dayflow.demo", "password": "ChangeMe_Emp12!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Bad credentials."


async def test_activate_account_rejects_email_already_in_use(client: AsyncClient):
    suffix = uuid4().hex[:8]
    employee_code = f"DUP-{suffix[:4].upper()}"
    token = f"dup-email-token-{suffix}"
    password = "ChangeMe_Emp12!"

    async with SessionLocal() as session:
        org = await session.scalar(select(Organization).limit(1))
        hr = await session.scalar(select(User).where(User.email == settings.seed_hr_email))
        assert org is not None and hr is not None
        employee = Employee(
            organization_id=org.id,
            employee_code=employee_code,
            first_name="Dup",
            last_name="Email",
            status=EmployeeStatus.INVITED.value,
            joined_on=date(2026, 8, 1),
        )
        session.add(employee)
        await session.flush()
        session.add(
            AccountInvite(
                organization_id=org.id,
                employee_id=employee.id,
                email=settings.seed_employee_email,
                role=Role.EMPLOYEE.value,
                token_hash=_invite_token_hash(token),
                expires_at=datetime.now(UTC) + timedelta(days=7),
                created_by=hr.id,
            )
        )
        await session.commit()

    response = await client.post(
        "/api/auth/activate-account",
        json={
            "employee_code": employee_code,
            "email": settings.seed_employee_email,
            "token": token,
            "password": password,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "This email is already in use."


async def test_activate_account_rejects_second_invite_for_active_employee(client: AsyncClient):
    suffix = uuid4().hex[:8]
    email = f"second.{suffix}@dayflow.demo"
    later_email = f"later.{suffix}@dayflow.demo"
    employee_code = f"SEC-{suffix[:4].upper()}"
    token = f"first-invite-{suffix}"
    later_token = f"later-invite-{suffix}"
    password = "ChangeMe_Emp12!"

    async with SessionLocal() as session:
        org = await session.scalar(select(Organization).limit(1))
        hr = await session.scalar(select(User).where(User.email == settings.seed_hr_email))
        assert org is not None and hr is not None
        employee = Employee(
            organization_id=org.id,
            employee_code=employee_code,
            first_name="Second",
            last_name="Invite",
            status=EmployeeStatus.INVITED.value,
            joined_on=date(2026, 8, 1),
        )
        session.add(employee)
        await session.flush()
        session.add(
            AccountInvite(
                organization_id=org.id,
                employee_id=employee.id,
                email=email,
                role=Role.EMPLOYEE.value,
                token_hash=_invite_token_hash(token),
                expires_at=datetime.now(UTC) + timedelta(days=7),
                created_by=hr.id,
            )
        )
        await session.commit()
        employee_id = employee.id
        org_id = org.id
        hr_id = hr.id

    first = await client.post(
        "/api/auth/activate-account",
        json={
            "employee_code": employee_code,
            "email": email,
            "token": token,
            "password": password,
        },
    )
    assert first.status_code == 200

    async with SessionLocal() as session:
        session.add(
            AccountInvite(
                organization_id=org_id,
                employee_id=employee_id,
                email=later_email,
                role=Role.EMPLOYEE.value,
                token_hash=_invite_token_hash(later_token),
                expires_at=datetime.now(UTC) + timedelta(days=7),
                created_by=hr_id,
            )
        )
        await session.commit()

    second = await client.post(
        "/api/auth/activate-account",
        json={
            "employee_code": employee_code,
            "email": later_email,
            "token": later_token,
            "password": password,
        },
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "This account has already been activated."

    original = await client.post(
        "/api/auth/sign-in",
        json={"email": email, "password": password},
    )
    assert original.status_code == 200
    assert original.json()["user"]["employee_code"] == employee_code


async def test_sign_in_matches_email_case_insensitively(client: AsyncClient):
    suffix = uuid4().hex[:8]
    stored = f"Case.{suffix}@Dayflow.Demo"
    password = "ChangeMe_Emp12!"
    async with SessionLocal() as session:
        org = await session.scalar(select(Organization).limit(1))
        assert org is not None
        user = User(
            email=stored,
            password_hash=hash_password(password),
            status=UserStatus.ACTIVE.value,
        )
        session.add(user)
        await session.flush()
        session.add(
            OrganizationMembership(
                organization_id=org.id, user_id=user.id, role=Role.EMPLOYEE.value
            )
        )
        session.add(
            Employee(
                organization_id=org.id,
                user_id=user.id,
                employee_code=f"CS-{suffix[:4].upper()}",
                first_name="Case",
                last_name="Fold",
                status=EmployeeStatus.ACTIVE.value,
                joined_on=date(2026, 1, 1),
            )
        )
        await session.commit()

    response = await client.post(
        "/api/auth/sign-in",
        json={"email": stored.lower(), "password": password},
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"].lower() == stored.lower()


async def test_activate_account_stores_normalized_email(client: AsyncClient):
    suffix = uuid4().hex[:8]
    invite_email = f"mixed.{suffix}@dayflow.demo"
    employee_code = f"MIX-{suffix[:4].upper()}"
    token = f"mixed-case-token-{suffix}"
    password = "ChangeMe_Emp12!"

    async with SessionLocal() as session:
        org = await session.scalar(select(Organization).limit(1))
        hr = await session.scalar(select(User).where(User.email == settings.seed_hr_email))
        assert org is not None and hr is not None
        employee = Employee(
            organization_id=org.id,
            employee_code=employee_code,
            first_name="Mixed",
            last_name="Case",
            status=EmployeeStatus.INVITED.value,
            joined_on=date(2026, 8, 1),
        )
        session.add(employee)
        await session.flush()
        session.add(
            AccountInvite(
                organization_id=org.id,
                employee_id=employee.id,
                email=invite_email.upper(),
                role=Role.EMPLOYEE.value,
                token_hash=_invite_token_hash(token),
                expires_at=datetime.now(UTC) + timedelta(days=7),
                created_by=hr.id,
            )
        )
        await session.commit()

    response = await client.post(
        "/api/auth/activate-account",
        json={
            "employee_code": employee_code,
            "email": invite_email,
            "token": token,
            "password": password,
        },
    )
    assert response.status_code == 200
    signed_in = await client.post(
        "/api/auth/sign-in",
        json={"email": invite_email.upper(), "password": password},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["user"]["email"] == invite_email
