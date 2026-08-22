from datetime import UTC, date, datetime
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.domain.roles import EmployeeStatus, Role, UserStatus
from app.models import (
    AuditEvent,
    Employee,
    Holiday,
    LeaveBalance,
    LeaveRequest,
    LeaveRequestEvent,
    LeaveType,
    Organization,
    OrganizationMembership,
    User,
)

PASSWORD = "ChangeMe_Emp12!"


async def _sign_in(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post("/api/auth/sign-in", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()


def _select_org():
    return select(Organization).where(Organization.name == "Dayflow Demo")


async def _create_employee_with_balances() -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    email = f"leave.{suffix}@dayflow.demo"
    async with SessionLocal() as session:
        org = await session.scalar(_select_org())
        assert org is not None
        user = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            email_verified_at=datetime.now(UTC),
            status=UserStatus.ACTIVE.value,
        )
        session.add(user)
        await session.flush()
        session.add(
            OrganizationMembership(
                organization_id=org.id,
                user_id=user.id,
                role=Role.EMPLOYEE.value,
            )
        )
        employee = Employee(
            organization_id=org.id,
            user_id=user.id,
            employee_code=f"LV-{suffix[:4].upper()}",
            first_name="Lea",
            last_name=suffix[:4].upper(),
            status=EmployeeStatus.ACTIVE.value,
            joined_on=date(2026, 1, 1),
        )
        session.add(employee)
        await session.flush()
        types = list(
            await session.scalars(select(LeaveType).where(LeaveType.organization_id == org.id))
        )
        by_code = {row.code: row for row in types}
        session.add_all(
            [
                LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=by_code["PAID"].id,
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 12, 31),
                    granted_days=18,
                ),
                LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=by_code["SICK"].id,
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 12, 31),
                    granted_days=8,
                ),
                LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=by_code["UNPAID"].id,
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 12, 31),
                    granted_days=0,
                ),
            ]
        )
        await session.commit()
    return email, PASSWORD


async def test_employee_submits_paid_range_excluding_weekends_and_holidays(client: AsyncClient):
    email, password = await _create_employee_with_balances()
    session = await _sign_in(client, email, password)
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    employee_id = session["user"]["employee_id"]

    async with SessionLocal() as db:
        org = await db.scalar(_select_org())
        assert org is not None
        db.add(Holiday(organization_id=org.id, name="Midweek holiday", date=date(2026, 8, 26)))
        await db.commit()

    created = await client.post(
        "/api/time-off/requests",
        headers=headers,
        json={
            "leave_type": "PAID",
            "starts_on": "2026-08-21",
            "ends_on": "2026-08-26",
            "reason": "Family visit covering a weekend and holiday.",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["leave_type"] == "PAID"
    assert body["starts_on"] == "2026-08-21"
    assert body["ends_on"] == "2026-08-26"
    assert body["status"] == "PENDING"
    assert body["reason"] == "Family visit covering a weekend and holiday."
    assert body["employee_id"] == employee_id
    # Fri 21 work, Sat 22 weekend, Sun 23 weekend, Mon 24 work, Tue 25 work, Wed 26 holiday.
    assert body["counted_days"] == 3

    home = await client.get("/api/time-off", headers=headers)
    assert home.status_code == 200
    payload = home.json()
    assert payload["role"] == "EMPLOYEE"
    assert payload["employee_id"] == employee_id
    paid = next(row for row in payload["balances"] if row["leave_type"] == "PAID")
    assert paid["remaining_days"] == 18
    assert payload["pending_queue"] == []
    assert len(payload["requests"]) == 1
    assert payload["requests"][0]["id"] == body["id"]
    assert payload["requests"][0]["counted_days"] == 3
    assert payload["requests"][0]["status"] == "PENDING"


async def test_pending_or_approved_overlap_is_rejected(client: AsyncClient):
    email, password = await _create_employee_with_balances()
    session = await _sign_in(client, email, password)
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    first = await client.post(
        "/api/time-off/requests",
        headers=headers,
        json={
            "leave_type": "PAID",
            "starts_on": "2026-09-07",
            "ends_on": "2026-09-09",
            "reason": "First pending range.",
        },
    )
    assert first.status_code == 200
    assert first.json()["counted_days"] == 3

    overlap = await client.post(
        "/api/time-off/requests",
        headers=headers,
        json={
            "leave_type": "SICK",
            "starts_on": "2026-09-09",
            "ends_on": "2026-09-11",
            "reason": "Overlaps the pending request.",
        },
    )
    assert overlap.status_code == 409
    assert overlap.json()["detail"] == "Leave range overlaps a pending or approved request."

    listed = await client.get("/api/time-off", headers=headers)
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()["requests"]] == [first.json()["id"]]


async def test_employee_cancels_pending_only(client: AsyncClient):
    email, password = await _create_employee_with_balances()
    other_email, other_password = await _create_employee_with_balances()
    session = await _sign_in(client, email, password)
    other = await _sign_in(client, other_email, other_password)
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    created = await client.post(
        "/api/time-off/requests",
        headers=headers,
        json={
            "leave_type": "PAID",
            "starts_on": "2026-10-05",
            "ends_on": "2026-10-06",
            "reason": "Cancelable pending request.",
        },
    )
    assert created.status_code == 200
    request_id = created.json()["id"]

    foreign = await client.post(
        f"/api/time-off/requests/{request_id}/cancel",
        headers=other_headers,
    )
    assert foreign.status_code == 403
    assert foreign.json()["detail"] == "Employees can cancel only their own pending requests."

    cancelled = await client.post(
        f"/api/time-off/requests/{request_id}/cancel",
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["id"] == request_id
    assert cancelled.json()["status"] == "CANCELLED"

    listed = await client.get("/api/time-off", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["requests"][0]["status"] == "CANCELLED"

    again = await client.post(
        "/api/time-off/requests",
        headers=headers,
        json={
            "leave_type": "PAID",
            "starts_on": "2026-10-05",
            "ends_on": "2026-10-06",
            "reason": "Same dates after cancel.",
        },
    )
    assert again.status_code == 200
    assert again.json()["status"] == "PENDING"

    second_cancel = await client.post(
        f"/api/time-off/requests/{request_id}/cancel",
        headers=headers,
    )
    assert second_cancel.status_code == 400
    assert second_cancel.json()["detail"] == "Only pending leave requests can be cancelled."


async def test_insufficient_paid_balance_fails_unpaid_does_not(client: AsyncClient):
    email, password = await _create_employee_with_balances()
    session = await _sign_in(client, email, password)
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    paid = await client.post(
        "/api/time-off/requests",
        headers=headers,
        json={
            "leave_type": "PAID",
            "starts_on": "2026-01-01",
            "ends_on": "2026-01-30",
            "reason": "More paid days than remaining.",
        },
    )
    assert paid.status_code == 400
    assert paid.json()["detail"] == "Insufficient leave balance."

    unpaid = await client.post(
        "/api/time-off/requests",
        headers=headers,
        json={
            "leave_type": "UNPAID",
            "starts_on": "2026-01-01",
            "ends_on": "2026-01-30",
            "reason": "Unpaid does not consume a balance.",
        },
    )
    assert unpaid.status_code == 200
    assert unpaid.json()["leave_type"] == "UNPAID"
    assert unpaid.json()["status"] == "PENDING"
    assert unpaid.json()["counted_days"] == 22

    sick = await client.post(
        "/api/time-off/requests",
        headers=headers,
        json={
            "leave_type": "SICK",
            "starts_on": "2026-02-02",
            "ends_on": "2026-02-03",
            "reason": "Fever.",
        },
    )
    assert sick.status_code == 200
    assert sick.json()["leave_type"] == "SICK"
    assert sick.json()["counted_days"] == 2

    home = await client.get("/api/time-off", headers=headers)
    assert home.status_code == 200
    statuses = {row["leave_type"]: row["status"] for row in home.json()["requests"]}
    assert statuses["UNPAID"] == "PENDING"
    assert statuses["SICK"] == "PENDING"
    assert "PAID" not in statuses


async def test_hr_approve_updates_used_days_and_writes_event_and_audit(client: AsyncClient):
    email, password = await _create_employee_with_balances()
    actor = await _sign_in(client, email, password)
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {actor['access_token']}"}
    hr_headers = {"Authorization": f"Bearer {hr['access_token']}"}
    employee_id = actor["user"]["employee_id"]

    created = await client.post(
        "/api/time-off/requests",
        headers=headers,
        json={
            "leave_type": "PAID",
            "starts_on": "2026-11-02",
            "ends_on": "2026-11-04",
            "reason": "Need three paid days.",
        },
    )
    assert created.status_code == 200
    assert created.json()["counted_days"] == 3
    request_id = created.json()["id"]

    employee_approve = await client.post(
        f"/api/time-off/requests/{request_id}/approve",
        headers=headers,
        json={"comment": "Self approve"},
    )
    assert employee_approve.status_code == 403
    assert employee_approve.json()["detail"] == "HR role required."

    hr_home = await client.get("/api/time-off", headers=hr_headers)
    assert hr_home.status_code == 200
    assert hr_home.json()["role"] == "HR"
    pending = [row for row in hr_home.json()["pending_queue"] if row["id"] == request_id]
    assert pending
    assert pending[0]["status"] == "PENDING"
    assert pending[0]["employee_id"] == employee_id
    assert pending[0]["leave_type"] == "PAID"
    assert pending[0]["employee_name"]

    approved = await client.post(
        f"/api/time-off/requests/{request_id}/approve",
        headers=hr_headers,
        json={"comment": "Coverage confirmed."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["review_comment"] == "Coverage confirmed."

    employee_home = await client.get("/api/time-off", headers=headers)
    assert employee_home.status_code == 200
    paid = next(row for row in employee_home.json()["balances"] if row["leave_type"] == "PAID")
    assert paid["used_days"] == 3
    assert paid["remaining_days"] == 15
    assert employee_home.json()["requests"][0]["status"] == "APPROVED"

    after_hr = await client.get("/api/time-off", headers=hr_headers)
    assert after_hr.status_code == 200
    assert all(row["id"] != request_id for row in after_hr.json()["pending_queue"])

    async with SessionLocal() as db:
        events = list(
            await db.scalars(
                select(LeaveRequestEvent)
                .where(LeaveRequestEvent.leave_request_id == request_id)
                .order_by(LeaveRequestEvent.created_at)
            )
        )
        assert events
        assert events[-1].from_status == "PENDING"
        assert events[-1].to_status == "APPROVED"
        assert str(events[-1].actor_user_id) == hr["user"]["id"]
        assert events[-1].comment == "Coverage confirmed."
        audit = await db.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "leave_request",
                AuditEvent.entity_id == request_id,
                AuditEvent.action == "leave.request.approve",
            )
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit is not None
        assert str(audit.actor_user_id) == hr["user"]["id"]
        assert audit.after_json is not None
        assert audit.after_json["status"] == "APPROVED"
        assert audit.after_json["used_days"] == 3
        assert audit.before_json is not None
        assert audit.before_json["status"] == "PENDING"
        assert audit.before_json["used_days"] == 0


async def test_hr_reject_requires_comment_and_does_not_consume_balance(client: AsyncClient):
    email, password = await _create_employee_with_balances()
    actor = await _sign_in(client, email, password)
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {actor['access_token']}"}
    hr_headers = {"Authorization": f"Bearer {hr['access_token']}"}

    created = await client.post(
        "/api/time-off/requests",
        headers=headers,
        json={
            "leave_type": "PAID",
            "starts_on": "2026-12-01",
            "ends_on": "2026-12-02",
            "reason": "Short paid trip.",
        },
    )
    assert created.status_code == 200
    request_id = created.json()["id"]

    missing = await client.post(
        f"/api/time-off/requests/{request_id}/reject",
        headers=hr_headers,
        json={"comment": ""},
    )
    assert missing.status_code == 400
    assert missing.json()["detail"] == "Rejection requires a comment."

    still_pending = await client.get("/api/time-off", headers=headers)
    assert still_pending.status_code == 200
    assert still_pending.json()["requests"][0]["status"] == "PENDING"
    paid = next(row for row in still_pending.json()["balances"] if row["leave_type"] == "PAID")
    assert paid["used_days"] == 0
    assert paid["remaining_days"] == 18

    rejected = await client.post(
        f"/api/time-off/requests/{request_id}/reject",
        headers=hr_headers,
        json={"comment": "Team already short that week."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["review_comment"] == "Team already short that week."

    home = await client.get("/api/time-off", headers=headers)
    assert home.status_code == 200
    assert home.json()["requests"][0]["status"] == "REJECTED"
    paid = next(row for row in home.json()["balances"] if row["leave_type"] == "PAID")
    assert paid["used_days"] == 0
    assert paid["remaining_days"] == 18

    retry_same_dates = await client.post(
        "/api/time-off/requests",
        headers=headers,
        json={
            "leave_type": "PAID",
            "starts_on": "2026-12-01",
            "ends_on": "2026-12-02",
            "reason": "Rejected range can be requested again.",
        },
    )
    assert retry_same_dates.status_code == 200
    assert retry_same_dates.json()["status"] == "PENDING"

    async with SessionLocal() as db:
        event = await db.scalar(
            select(LeaveRequestEvent)
            .where(
                LeaveRequestEvent.leave_request_id == request_id,
                LeaveRequestEvent.to_status == "REJECTED",
            )
            .order_by(LeaveRequestEvent.created_at.desc())
        )
        assert event is not None
        assert event.from_status == "PENDING"
        assert event.comment == "Team already short that week."
        audit = await db.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "leave_request",
                AuditEvent.entity_id == request_id,
                AuditEvent.action == "leave.request.reject",
            )
            .order_by(AuditEvent.created_at.desc())
        )
        assert audit is not None
        assert audit.after_json is not None
        assert audit.after_json["status"] == "REJECTED"
        assert audit.after_json["used_days"] == 0


async def test_time_off_queries_and_reviews_are_organization_scoped(client: AsyncClient):
    suffix = uuid4().hex[:8]
    other_email = f"hr.leave.{suffix}@dayflow.demo"
    other_password = "ChangeMe_Other12!"
    foreign_request_id = None

    async with SessionLocal() as session:
        other_org = Organization(name=f"Other Co Leave {suffix}", timezone="Asia/Kolkata", currency="INR")
        session.add(other_org)
        await session.flush()
        other_hr = User(
            email=other_email,
            password_hash=hash_password(other_password),
            status=UserStatus.ACTIVE.value,
            email_verified_at=datetime.now(UTC),
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
            employee_code=f"XL-{suffix[:4].upper()}",
            first_name="Foreign",
            last_name="Leave",
            status=EmployeeStatus.ACTIVE.value,
            joined_on=date(2026, 1, 1),
        )
        session.add(foreign_employee)
        await session.flush()
        foreign_type = LeaveType(
            organization_id=other_org.id,
            name="Paid leave",
            code="PAID",
            is_paid=True,
            requires_balance=True,
        )
        session.add(foreign_type)
        await session.flush()
        session.add(
            LeaveRequest(
                employee_id=foreign_employee.id,
                leave_type_id=foreign_type.id,
                starts_on=date(2026, 9, 14),
                ends_on=date(2026, 9, 15),
                counted_days=2,
                reason="Foreign org pending leave.",
                status="PENDING",
                submitted_at=datetime.now(UTC),
            )
        )
        await session.commit()
        stored = await session.scalar(
            select(LeaveRequest).where(LeaveRequest.employee_id == foreign_employee.id)
        )
        assert stored is not None
        foreign_request_id = str(stored.id)

    demo_hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {demo_hr['access_token']}"}

    listed = await client.get("/api/time-off", headers=headers)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["requests"]}
    pending_ids = {row["id"] for row in listed.json()["pending_queue"]}
    assert foreign_request_id not in ids
    assert foreign_request_id not in pending_ids

    approve = await client.post(
        f"/api/time-off/requests/{foreign_request_id}/approve",
        headers=headers,
        json={"comment": "Should not cross orgs."},
    )
    assert approve.status_code == 404
    assert approve.json()["detail"] == "Leave request not found."

    reject = await client.post(
        f"/api/time-off/requests/{foreign_request_id}/reject",
        headers=headers,
        json={"comment": "Should not cross orgs."},
    )
    assert reject.status_code == 404
    assert reject.json()["detail"] == "Leave request not found."

    employee = await _sign_in(client, "employee@dayflow.demo", "ChangeMe_Emp12!")
    employee_headers = {"Authorization": f"Bearer {employee['access_token']}"}
    cancel = await client.post(
        f"/api/time-off/requests/{foreign_request_id}/cancel",
        headers=employee_headers,
    )
    assert cancel.status_code == 404
    assert cancel.json()["detail"] == "Leave request not found."

    unauth = await client.get("/api/time-off")
    assert unauth.status_code == 401
    assert unauth.json()["detail"] == "Not signed in."
    unauth_post = await client.post(
        "/api/time-off/requests",
        json={
            "leave_type": "PAID",
            "starts_on": "2026-09-14",
            "ends_on": "2026-09-15",
            "reason": "Unauthenticated.",
        },
    )
    assert unauth_post.status_code == 401
    assert unauth_post.json()["detail"] == "Not signed in."

    async with SessionLocal() as session:
        pending = await session.get(LeaveRequest, foreign_request_id)
        assert pending is not None
        assert pending.status == "PENDING"


async def test_employee_sees_only_own_leave_requests(client: AsyncClient):
    first_email, first_password = await _create_employee_with_balances()
    second_email, second_password = await _create_employee_with_balances()
    first = await _sign_in(client, first_email, first_password)
    second = await _sign_in(client, second_email, second_password)
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}

    created = await client.post(
        "/api/time-off/requests",
        headers=first_headers,
        json={
            "leave_type": "PAID",
            "starts_on": "2026-06-01",
            "ends_on": "2026-06-02",
            "reason": "Own request only.",
        },
    )
    assert created.status_code == 200
    request_id = created.json()["id"]

    first_home = await client.get("/api/time-off", headers=first_headers)
    assert first_home.status_code == 200
    assert {row["id"] for row in first_home.json()["requests"]} == {request_id}
    assert first_home.json()["pending_queue"] == []

    second_home = await client.get("/api/time-off", headers=second_headers)
    assert second_home.status_code == 200
    assert request_id not in {row["id"] for row in second_home.json()["requests"]}
    assert second_home.json()["pending_queue"] == []

    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    hr_home = await client.get("/api/time-off", headers={"Authorization": f"Bearer {hr['access_token']}"})
    assert hr_home.status_code == 200
    assert request_id in {row["id"] for row in hr_home.json()["pending_queue"]}
