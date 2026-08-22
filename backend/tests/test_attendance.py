from datetime import UTC, date, datetime
from uuid import uuid4

from httpx import AsyncClient

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.domain.roles import EmployeeStatus, Role, UserStatus
from app.models import (
    AttendanceCorrectionRequest,
    AttendanceSession,
    Employee,
    LeaveRequest,
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


async def _create_active_employee(*, role: Role = Role.EMPLOYEE) -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    email = f"att.{suffix}@dayflow.demo"
    async with SessionLocal() as session:
        org = await session.scalar(select_org())
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
                role=role.value,
            )
        )
        employee = Employee(
            organization_id=org.id,
            user_id=user.id,
            employee_code=f"ATT-{suffix[:4].upper()}",
            first_name="Att",
            last_name=suffix[:4].upper(),
            status=EmployeeStatus.ACTIVE.value,
            joined_on=date(2026, 1, 1),
        )
        session.add(employee)
        await session.commit()
    return email, PASSWORD


def select_org():
    from sqlalchemy import select

    return select(Organization).where(Organization.name == "Dayflow Demo")


async def test_employee_check_in_uses_server_time_and_opens_one_session(client: AsyncClient):
    email, password = await _create_active_employee()
    session = await _sign_in(client, email, password)
    token = session["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    employee_id = session["user"]["employee_id"]

    forged = "2020-01-01T00:00:00+00:00"
    before = datetime.now(UTC)
    response = await client.post(
        "/api/attendance/check-in",
        headers=headers,
        json={"check_in_at": forged, "work_date": "2020-01-01"},
    )
    after = datetime.now(UTC)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "OPEN"
    assert body["source"] == "SERVER"
    assert body["check_out_at"] is None
    assert body["worked_minutes"] is None
    assert body["employee_id"] == employee_id
    check_in_at = datetime.fromisoformat(body["check_in_at"].replace("Z", "+00:00"))
    assert before <= check_in_at <= after
    assert "2020-01-01" not in body["check_in_at"]
    assert body["work_date"] != "2020-01-01"

    listed = await client.get("/api/attendance", headers=headers)
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["role"] == "EMPLOYEE"
    assert payload["employee_id"] == employee_id
    assert payload["open_session"] is not None
    assert payload["open_session"]["id"] == body["id"]
    assert payload["open_session"]["check_in_at"] == body["check_in_at"]
    assert len(payload["sessions"]) == 1
    assert payload["sessions"][0]["id"] == body["id"]
    assert payload["sessions"][0]["status"] == "OPEN"
    assert payload["sessions"][0]["check_in_at"] == body["check_in_at"]


async def test_second_check_in_with_open_session_fails(client: AsyncClient):
    email, password = await _create_active_employee()
    session = await _sign_in(client, email, password)
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    first = await client.post("/api/attendance/check-in", headers=headers)
    assert first.status_code == 200
    first_id = first.json()["id"]

    second = await client.post("/api/attendance/check-in", headers=headers)
    assert second.status_code == 409
    assert second.json()["detail"] == "An open attendance session already exists."

    listed = await client.get("/api/attendance", headers=headers)
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["open_session"]["id"] == first_id
    assert [row["id"] for row in payload["sessions"]] == [first_id]


async def test_check_out_after_check_in_closes_session_and_stores_worked_minutes(client: AsyncClient):
    email, password = await _create_active_employee()
    session = await _sign_in(client, email, password)
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    inbound = await client.post("/api/attendance/check-in", headers=headers)
    assert inbound.status_code == 200
    check_in_at = datetime.fromisoformat(inbound.json()["check_in_at"].replace("Z", "+00:00"))

    outbound = await client.post("/api/attendance/check-out", headers=headers)
    assert outbound.status_code == 200
    body = outbound.json()
    assert body["id"] == inbound.json()["id"]
    assert body["status"] != "OPEN"
    assert body["check_out_at"] is not None
    check_out_at = datetime.fromisoformat(body["check_out_at"].replace("Z", "+00:00"))
    assert check_out_at > check_in_at
    expected_minutes = int((check_out_at - check_in_at).total_seconds() // 60)
    assert body["worked_minutes"] == expected_minutes

    listed = await client.get("/api/attendance", headers=headers)
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["open_session"] is None
    assert payload["sessions"][0]["id"] == body["id"]
    assert payload["sessions"][0]["worked_minutes"] == expected_minutes
    assert payload["sessions"][0]["check_out_at"] == body["check_out_at"]

    again = await client.post("/api/attendance/check-out", headers=headers)
    assert again.status_code == 400
    assert again.json()["detail"] == "No open attendance session to close."


async def test_approved_leave_blocks_check_in(client: AsyncClient):
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    from sqlalchemy import select

    email, password = await _create_active_employee()
    session = await _sign_in(client, email, password)
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    employee_id = session["user"]["employee_id"]

    async with SessionLocal() as db:
        org = await db.scalar(select(Organization).where(Organization.name == "Dayflow Demo"))
        assert org is not None
        leave_type = await db.scalar(
            select(LeaveType).where(
                LeaveType.organization_id == org.id,
                LeaveType.code == "PAID",
            )
        )
        assert leave_type is not None
        today = datetime.now(UTC).astimezone(ZoneInfo(org.timezone)).date()
        db.add(
            LeaveRequest(
                employee_id=employee_id,
                leave_type_id=leave_type.id,
                starts_on=today,
                ends_on=today + timedelta(days=1),
                counted_days=1,
                reason="Approved leave blocks attendance.",
                status="APPROVED",
                submitted_at=datetime.now(UTC),
            )
        )
        await db.commit()

    blocked = await client.post("/api/attendance/check-in", headers=headers)
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "Employee is on approved leave."

    listed = await client.get("/api/attendance", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["open_session"] is None
    assert listed.json()["sessions"] == []


async def test_employee_sees_only_own_sessions_hr_sees_org_sessions(client: AsyncClient):
    first_email, first_password = await _create_active_employee()
    second_email, second_password = await _create_active_employee()
    first = await _sign_in(client, first_email, first_password)
    second = await _sign_in(client, second_email, second_password)
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")

    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    hr_headers = {"Authorization": f"Bearer {hr['access_token']}"}

    first_in = await client.post("/api/attendance/check-in", headers=first_headers)
    second_in = await client.post("/api/attendance/check-in", headers=second_headers)
    assert first_in.status_code == 200
    assert second_in.status_code == 200
    first_id = first_in.json()["id"]
    second_id = second_in.json()["id"]
    assert first_id != second_id

    first_list = await client.get("/api/attendance", headers=first_headers)
    assert first_list.status_code == 200
    first_ids = {row["id"] for row in first_list.json()["sessions"]}
    assert first_ids == {first_id}
    assert first_list.json()["open_session"]["id"] == first_id

    second_list = await client.get("/api/attendance", headers=second_headers)
    assert second_list.status_code == 200
    second_ids = {row["id"] for row in second_list.json()["sessions"]}
    assert second_ids == {second_id}

    hr_list = await client.get("/api/attendance", headers=hr_headers)
    assert hr_list.status_code == 200
    assert hr_list.json()["role"] == "HR"
    hr_ids = {row["id"] for row in hr_list.json()["sessions"]}
    assert first_id in hr_ids
    assert second_id in hr_ids

    unauth = await client.get("/api/attendance")
    assert unauth.status_code == 401
    assert unauth.json()["detail"] == "Not signed in."


async def test_historical_punches_change_only_via_hr_correction_with_audit(client: AsyncClient):
    from sqlalchemy import select

    from app.models import AuditEvent

    email, password = await _create_active_employee()
    other_email, other_password = await _create_active_employee()
    actor = await _sign_in(client, email, password)
    other = await _sign_in(client, other_email, other_password)
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {actor['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    hr_headers = {"Authorization": f"Bearer {hr['access_token']}"}
    employee_id = actor["user"]["employee_id"]

    original_in = datetime(2026, 8, 20, 4, 0, tzinfo=UTC)
    original_out = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
    proposed_in = datetime(2026, 8, 20, 3, 30, tzinfo=UTC)
    proposed_out = datetime(2026, 8, 20, 12, 30, tzinfo=UTC)

    async with SessionLocal() as db:
        session_row = AttendanceSession(
            employee_id=employee_id,
            work_date=date(2026, 8, 20),
            check_in_at=original_in,
            check_out_at=original_out,
            source="SERVER",
            status="PRESENT",
            worked_minutes=480,
        )
        db.add(session_row)
        await db.commit()
        await db.refresh(session_row)
        session_id = str(session_row.id)

    listed = await client.get("/api/attendance", headers=headers)
    assert listed.status_code == 200
    row = next(item for item in listed.json()["sessions"] if item["id"] == session_id)
    assert row["check_in_at"].startswith("2026-08-20T04:00:00")
    assert row["check_out_at"].startswith("2026-08-20T12:00:00")
    assert row["worked_minutes"] == 480

    foreign = await client.post(
        "/api/attendance/corrections",
        headers=other_headers,
        json={
            "attendance_session_id": session_id,
            "proposed_check_in_at": proposed_in.isoformat(),
            "proposed_check_out_at": proposed_out.isoformat(),
            "reason": "Trying to change someone else's punches.",
        },
    )
    assert foreign.status_code == 403
    assert foreign.json()["detail"] == "Employees can correct only their own attendance."

    created = await client.post(
        "/api/attendance/corrections",
        headers=headers,
        json={
            "attendance_session_id": session_id,
            "proposed_check_in_at": proposed_in.isoformat(),
            "proposed_check_out_at": proposed_out.isoformat(),
            "reason": "Forgot to punch at the door.",
        },
    )
    assert created.status_code == 200
    correction = created.json()
    assert correction["attendance_session_id"] == session_id
    assert correction["status"] == "PENDING"
    assert correction["reason"] == "Forgot to punch at the door."
    assert correction["proposed_check_in_at"].startswith("2026-08-20T03:30:00")
    assert correction["proposed_check_out_at"].startswith("2026-08-20T12:30:00")
    correction_id = correction["id"]

    still_original = await client.get("/api/attendance", headers=headers)
    row = next(item for item in still_original.json()["sessions"] if item["id"] == session_id)
    assert row["check_in_at"].startswith("2026-08-20T04:00:00")
    assert row["check_out_at"].startswith("2026-08-20T12:00:00")
    assert row["worked_minutes"] == 480

    employee_review = await client.post(
        f"/api/attendance/corrections/{correction_id}/review",
        headers=headers,
        json={"decision": "APPROVED", "comment": "Self approve"},
    )
    assert employee_review.status_code == 403
    assert employee_review.json()["detail"] == "HR role required."

    hr_home = await client.get("/api/attendance", headers=hr_headers)
    assert hr_home.status_code == 200
    pending = [item for item in hr_home.json()["exceptions"] if item["id"] == correction_id]
    assert pending
    assert pending[0]["kind"] == "correction_pending"
    assert pending[0]["status"] == "PENDING"
    assert pending[0]["employee_id"] == employee_id

    reviewed = await client.post(
        f"/api/attendance/corrections/{correction_id}/review",
        headers=hr_headers,
        json={"decision": "APPROVED", "comment": "Badge log matches the request."},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "APPROVED"
    assert reviewed.json()["review_comment"] == "Badge log matches the request."
    assert reviewed.json()["reviewed_by"] == hr["user"]["id"]

    updated = await client.get("/api/attendance", headers=headers)
    row = next(item for item in updated.json()["sessions"] if item["id"] == session_id)
    assert row["check_in_at"].startswith("2026-08-20T03:30:00")
    assert row["check_out_at"].startswith("2026-08-20T12:30:00")
    assert row["worked_minutes"] == 540

    async with SessionLocal() as db:
        event = await db.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "attendance_correction",
                AuditEvent.entity_id == correction_id,
                AuditEvent.action == "attendance.correction.approve",
            )
            .order_by(AuditEvent.created_at.desc())
        )
        assert event is not None
        assert event.actor_user_id is not None
        assert str(event.actor_user_id) == hr["user"]["id"]
        assert event.after_json is not None
        assert event.after_json["check_in_at"].startswith("2026-08-20T03:30:00")
        assert event.after_json["check_out_at"].startswith("2026-08-20T12:30:00")
        assert event.after_json["worked_minutes"] == 540
        assert event.before_json is not None
        assert event.before_json["check_in_at"].startswith("2026-08-20T04:00:00")
        assert event.before_json["worked_minutes"] == 480


async def test_attendance_queries_and_reviews_are_organization_scoped(client: AsyncClient):
    suffix = uuid4().hex[:8]
    other_email = f"hr.att.{suffix}@dayflow.demo"
    other_password = "ChangeMe_Other12!"
    foreign_session_id = None
    foreign_correction_id = None

    async with SessionLocal() as session:
        other_org = Organization(name=f"Other Co Att {suffix}", timezone="Asia/Kolkata", currency="INR")
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
            employee_code=f"XA-{suffix[:4].upper()}",
            first_name="Foreign",
            last_name="Punch",
            status=EmployeeStatus.ACTIVE.value,
            joined_on=date(2026, 1, 1),
        )
        session.add(foreign_employee)
        await session.flush()
        punch = AttendanceSession(
            employee_id=foreign_employee.id,
            work_date=date(2026, 8, 19),
            check_in_at=datetime(2026, 8, 19, 3, 30, tzinfo=UTC),
            check_out_at=datetime(2026, 8, 19, 12, 30, tzinfo=UTC),
            source="SERVER",
            status="PRESENT",
            worked_minutes=540,
        )
        session.add(punch)
        await session.flush()
        correction = AttendanceCorrectionRequest(
            attendance_session_id=punch.id,
            requested_by=other_hr.id,
            proposed_check_in_at=datetime(2026, 8, 19, 3, 0, tzinfo=UTC),
            proposed_check_out_at=datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
            reason="Foreign org correction.",
            status="PENDING",
        )
        session.add(correction)
        await session.commit()
        foreign_session_id = str(punch.id)
        foreign_correction_id = str(correction.id)

    demo_hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    token = demo_hr["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    listed = await client.get("/api/attendance", headers=headers)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["sessions"]}
    assert foreign_session_id not in ids
    exception_ids = {row["id"] for row in listed.json()["exceptions"]}
    assert foreign_correction_id not in exception_ids

    review = await client.post(
        f"/api/attendance/corrections/{foreign_correction_id}/review",
        headers=headers,
        json={"decision": "APPROVED", "comment": "Should not cross orgs."},
    )
    assert review.status_code == 404
    assert review.json()["detail"] == "Correction request not found."

    created = await client.post(
        "/api/attendance/corrections",
        headers=headers,
        json={
            "attendance_session_id": foreign_session_id,
            "proposed_check_in_at": "2026-08-19T03:00:00+00:00",
            "proposed_check_out_at": "2026-08-19T12:00:00+00:00",
            "reason": "Cross-org rewrite.",
        },
    )
    assert created.status_code == 404
    assert created.json()["detail"] == "Attendance session not found."

    async with SessionLocal() as session:
        punch = await session.get(AttendanceSession, foreign_session_id)
        assert punch is not None
        assert punch.worked_minutes == 540
        assert punch.check_in_at == datetime(2026, 8, 19, 3, 30, tzinfo=UTC)
        pending = await session.get(AttendanceCorrectionRequest, foreign_correction_id)
        assert pending is not None
        assert pending.status == "PENDING"


async def test_hr_rejection_keeps_historical_punches_and_writes_audit(client: AsyncClient):
    from sqlalchemy import select

    from app.models import AuditEvent

    email, password = await _create_active_employee()
    actor = await _sign_in(client, email, password)
    hr = await _sign_in(client, "hr@dayflow.demo", "ChangeMe_HR12!")
    headers = {"Authorization": f"Bearer {actor['access_token']}"}
    hr_headers = {"Authorization": f"Bearer {hr['access_token']}"}
    employee_id = actor["user"]["employee_id"]

    async with SessionLocal() as db:
        session_row = AttendanceSession(
            employee_id=employee_id,
            work_date=date(2026, 8, 18),
            check_in_at=datetime(2026, 8, 18, 4, 15, tzinfo=UTC),
            check_out_at=datetime(2026, 8, 18, 13, 15, tzinfo=UTC),
            source="SERVER",
            status="PRESENT",
            worked_minutes=540,
        )
        db.add(session_row)
        await db.commit()
        await db.refresh(session_row)
        session_id = str(session_row.id)

    created = await client.post(
        "/api/attendance/corrections",
        headers=headers,
        json={
            "attendance_session_id": session_id,
            "proposed_check_in_at": "2026-08-18T03:15:00+00:00",
            "proposed_check_out_at": "2026-08-18T12:15:00+00:00",
            "reason": "Wrong door time.",
        },
    )
    assert created.status_code == 200
    correction_id = created.json()["id"]

    missing_comment = await client.post(
        f"/api/attendance/corrections/{correction_id}/review",
        headers=hr_headers,
        json={"decision": "REJECTED", "comment": ""},
    )
    assert missing_comment.status_code == 400
    assert missing_comment.json()["detail"] == "Rejection requires a comment."

    rejected = await client.post(
        f"/api/attendance/corrections/{correction_id}/review",
        headers=hr_headers,
        json={"decision": "REJECTED", "comment": "Badge log does not match."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["review_comment"] == "Badge log does not match."

    listed = await client.get("/api/attendance", headers=headers)
    row = next(item for item in listed.json()["sessions"] if item["id"] == session_id)
    assert row["check_in_at"].startswith("2026-08-18T04:15:00")
    assert row["check_out_at"].startswith("2026-08-18T13:15:00")
    assert row["worked_minutes"] == 540

    async with SessionLocal() as db:
        event = await db.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "attendance_correction",
                AuditEvent.entity_id == correction_id,
                AuditEvent.action == "attendance.correction.reject",
            )
            .order_by(AuditEvent.created_at.desc())
        )
        assert event is not None
        assert event.after_json is not None
        assert event.after_json["check_in_at"].startswith("2026-08-18T04:15:00")
        assert event.after_json["worked_minutes"] == 540


async def test_attendance_mutations_require_auth(client: AsyncClient):
    check_in = await client.post("/api/attendance/check-in")
    assert check_in.status_code == 401
    assert check_in.json()["detail"] == "Not signed in."
    check_out = await client.post("/api/attendance/check-out")
    assert check_out.status_code == 401
    assert check_out.json()["detail"] == "Not signed in."
    correction = await client.post(
        "/api/attendance/corrections",
        json={
            "attendance_session_id": str(uuid4()),
            "proposed_check_in_at": "2026-08-18T03:15:00+00:00",
            "proposed_check_out_at": "2026-08-18T12:15:00+00:00",
            "reason": "Unauthenticated.",
        },
    )
    assert correction.status_code == 401
    assert correction.json()["detail"] == "Not signed in."
