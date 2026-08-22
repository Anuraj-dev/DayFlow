from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.deps import CurrentPrincipal, get_current_principal, require_hr
from app.core.db import get_db
from app.domain.attendance import (
    AttendanceError,
    AttendanceStatus,
    CorrectionStatus,
    assert_can_request_correction,
    assert_review_decision,
    can_check_in,
    can_check_out,
    derive_day_status,
    worked_minutes,
)
from app.domain.roles import Role
from app.models import (
    AttendanceCorrectionRequest,
    AttendanceSession,
    AuditEvent,
    Employee,
    LeaveRequest,
    Organization,
    WorkPolicy,
)
from app.schemas.attendance import (
    AttendanceExceptionOut,
    AttendanceHome,
    AttendanceSessionOut,
    CorrectionCreateRequest,
    CorrectionOut,
    CorrectionReviewRequest,
    OpenSessionOut,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _session_out(session: AttendanceSession) -> AttendanceSessionOut:
    return AttendanceSessionOut.model_validate(session)


def _correction_out(row: AttendanceCorrectionRequest) -> CorrectionOut:
    return CorrectionOut.model_validate(row)


def _punch_snapshot(session: AttendanceSession) -> dict:
    return {
        "session_id": str(session.id),
        "check_in_at": session.check_in_at.isoformat() if session.check_in_at else None,
        "check_out_at": session.check_out_at.isoformat() if session.check_out_at else None,
        "worked_minutes": session.worked_minutes,
        "status": session.status,
    }


async def _org_timezone(db: AsyncSession, organization_id) -> str:
    org = await db.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    return org.timezone


async def _on_leave(db: AsyncSession, employee_id, work_date) -> bool:
    leave_id = await db.scalar(
        select(LeaveRequest.id).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == "APPROVED",
            LeaveRequest.starts_on <= work_date,
            LeaveRequest.ends_on >= work_date,
        )
    )
    return leave_id is not None


async def _open_session(
    db: AsyncSession, employee_id, *, lock: bool = False
) -> AttendanceSession | None:
    query = (
        select(AttendanceSession)
        .where(
            AttendanceSession.employee_id == employee_id,
            AttendanceSession.status == AttendanceStatus.OPEN.value,
            AttendanceSession.check_out_at.is_(None),
        )
        .order_by(AttendanceSession.check_in_at.desc())
    )
    if lock:
        query = query.with_for_update()
    return await db.scalar(query)


def _require_employee(principal: CurrentPrincipal) -> None:
    if principal.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An employee record is required for attendance.",
        )


def _raise_attendance(exc: AttendanceError, *, conflict: bool = False) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT if conflict else status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    ) from exc


async def _apply_times(
    db: AsyncSession,
    session: AttendanceSession,
    *,
    organization_id: UUID,
    check_in_at: datetime,
    check_out_at: datetime | None,
) -> None:
    timezone_name = await _org_timezone(db, organization_id)
    policy = await db.scalar(select(WorkPolicy).where(WorkPolicy.organization_id == organization_id))
    full_day_minutes = policy.full_day_minutes if policy else 480
    half_day_minutes = policy.half_day_minutes if policy else 240
    late_after = policy.late_after_local_time if policy else None
    local_in = check_in_at.astimezone(ZoneInfo(timezone_name)).timetz().replace(tzinfo=None)
    late = bool(late_after and local_in > late_after)
    session.check_in_at = check_in_at
    session.check_out_at = check_out_at
    if check_out_at is None:
        session.worked_minutes = None
        session.status = AttendanceStatus.OPEN.value
        return
    minutes = worked_minutes(check_in_at, check_out_at)
    session.worked_minutes = minutes
    session.status = derive_day_status(
        on_leave=await _on_leave(db, session.employee_id, session.work_date),
        worked=minutes,
        full_day_minutes=full_day_minutes,
        half_day_minutes=half_day_minutes,
        late=late,
    ).value


async def _org_session(db: AsyncSession, organization_id: UUID, session_id: UUID) -> AttendanceSession:
    row = await db.scalar(
        select(AttendanceSession)
        .join(Employee, Employee.id == AttendanceSession.employee_id)
        .where(
            AttendanceSession.id == session_id,
            Employee.organization_id == organization_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance session not found.")
    return row


async def _pending_exceptions(
    db: AsyncSession, organization_id: UUID
) -> list[AttendanceExceptionOut]:
    employee = aliased(Employee)
    rows = (
        await db.execute(
            select(AttendanceCorrectionRequest, employee, AttendanceSession)
            .join(
                AttendanceSession,
                AttendanceSession.id == AttendanceCorrectionRequest.attendance_session_id,
            )
            .join(employee, employee.id == AttendanceSession.employee_id)
            .where(
                employee.organization_id == organization_id,
                AttendanceCorrectionRequest.status == CorrectionStatus.PENDING.value,
            )
            .order_by(AttendanceCorrectionRequest.created_at.desc())
        )
    ).all()
    exceptions: list[AttendanceExceptionOut] = []
    for correction, person, session_row in rows:
        exceptions.append(
            AttendanceExceptionOut(
                id=correction.id,
                employee_id=person.id,
                employee_name=f"{person.first_name} {person.last_name}",
                kind="correction_pending",
                status=correction.status,
                work_date=session_row.work_date,
                current_check_in_at=session_row.check_in_at,
                current_check_out_at=session_row.check_out_at,
                proposed_check_in_at=correction.proposed_check_in_at,
                proposed_check_out_at=correction.proposed_check_out_at,
                reason=correction.reason,
            )
        )
    open_missing = (
        await db.execute(
            select(AttendanceSession, employee)
            .join(employee, employee.id == AttendanceSession.employee_id)
            .where(
                employee.organization_id == organization_id,
                AttendanceSession.check_out_at.is_(None),
                AttendanceSession.status == AttendanceStatus.OPEN.value,
            )
        )
    ).all()
    for session, person in open_missing:
        exceptions.append(
            AttendanceExceptionOut(
                id=session.id,
                employee_id=session.employee_id,
                employee_name=f"{person.first_name} {person.last_name}",
                kind="missing_check_out",
                status=session.status,
                work_date=session.work_date,
                current_check_in_at=session.check_in_at,
            )
        )
    return exceptions


@router.get("", response_model=AttendanceHome)
async def list_attendance(
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AttendanceHome:
    query = (
        select(AttendanceSession)
        .join(Employee, Employee.id == AttendanceSession.employee_id)
        .where(Employee.organization_id == principal.organization_id)
        .order_by(AttendanceSession.work_date.desc(), AttendanceSession.check_in_at.desc())
    )
    if principal.role is not Role.HR:
        _require_employee(principal)
        query = query.where(AttendanceSession.employee_id == principal.employee_id)
    sessions = list(await db.scalars(query))
    open_row = None
    if principal.employee_id is not None:
        current = next(
            (
                row
                for row in sessions
                if row.employee_id == principal.employee_id and row.status == AttendanceStatus.OPEN.value
            ),
            None,
        )
        if current is not None:
            open_row = OpenSessionOut(id=current.id, check_in_at=current.check_in_at)
    exceptions: list[AttendanceExceptionOut] = []
    if principal.role is Role.HR:
        exceptions = await _pending_exceptions(db, principal.organization_id)
    return AttendanceHome(
        role=principal.role.value,
        employee_id=principal.employee_id,
        sessions=[_session_out(row) for row in sessions],
        open_session=open_row,
        exceptions=exceptions,
    )


@router.post("/check-in", response_model=AttendanceSessionOut)
async def check_in(
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AttendanceSessionOut:
    _require_employee(principal)
    timezone_name = await _org_timezone(db, principal.organization_id)
    now = datetime.now(UTC)
    work_date = now.astimezone(ZoneInfo(timezone_name)).date()
    open_row = await _open_session(db, principal.employee_id, lock=True)
    try:
        can_check_in(
            open_session_exists=open_row is not None,
            on_leave=await _on_leave(db, principal.employee_id, work_date),
        )
    except AttendanceError as exc:
        _raise_attendance(exc, conflict="open attendance session" in str(exc).lower())

    session = AttendanceSession(
        employee_id=principal.employee_id,
        work_date=work_date,
        check_in_at=now,
        check_out_at=None,
        source="SERVER",
        status=AttendanceStatus.OPEN.value,
        worked_minutes=None,
    )
    db.add(session)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An open attendance session already exists.",
        ) from exc
    await db.refresh(session)
    return _session_out(session)


@router.post("/check-out", response_model=AttendanceSessionOut)
async def check_out(
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AttendanceSessionOut:
    _require_employee(principal)
    open_row = await _open_session(db, principal.employee_id)
    now = datetime.now(UTC)
    try:
        can_check_out(check_in_at=open_row.check_in_at if open_row else None, check_out_at=now)
    except AttendanceError as exc:
        _raise_attendance(exc)
    assert open_row is not None
    await _apply_times(
        db,
        open_row,
        organization_id=principal.organization_id,
        check_in_at=open_row.check_in_at,
        check_out_at=now,
    )
    await db.commit()
    await db.refresh(open_row)
    return _session_out(open_row)


@router.post("/corrections", response_model=CorrectionOut)
async def request_correction(
    body: CorrectionCreateRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> CorrectionOut:
    session_row = await _org_session(db, principal.organization_id, body.attendance_session_id)
    try:
        assert_can_request_correction(
            is_hr=principal.role is Role.HR,
            actor_employee_id=principal.employee_id,
            session_employee_id=session_row.employee_id,
        )
        if body.proposed_check_out_at is not None:
            can_check_out(check_in_at=body.proposed_check_in_at, check_out_at=body.proposed_check_out_at)
    except AttendanceError as exc:
        forbidden = "only their own attendance" in str(exc)
        if forbidden:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        _raise_attendance(exc)
    if not body.reason.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A reason is required.")

    row = AttendanceCorrectionRequest(
        attendance_session_id=session_row.id,
        requested_by=principal.user_id,
        proposed_check_in_at=body.proposed_check_in_at,
        proposed_check_out_at=body.proposed_check_out_at,
        reason=body.reason.strip(),
        status=CorrectionStatus.PENDING.value,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _correction_out(row)


@router.post("/corrections/{correction_id}/review", response_model=CorrectionOut)
async def review_correction(
    correction_id: UUID,
    body: CorrectionReviewRequest,
    principal: CurrentPrincipal = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
) -> CorrectionOut:
    row = await db.scalar(
        select(AttendanceCorrectionRequest)
        .join(AttendanceSession, AttendanceSession.id == AttendanceCorrectionRequest.attendance_session_id)
        .join(Employee, Employee.id == AttendanceSession.employee_id)
        .where(
            AttendanceCorrectionRequest.id == correction_id,
            Employee.organization_id == principal.organization_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Correction request not found.")
    try:
        decision = assert_review_decision(
            current_status=row.status,
            decision=body.decision,
            comment=body.comment,
        )
    except AttendanceError as exc:
        _raise_attendance(exc)

    session_row = await db.get(AttendanceSession, row.attendance_session_id)
    if session_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance session not found.")
    before = _punch_snapshot(session_row)
    now = datetime.now(UTC)
    row.status = decision
    row.reviewed_by = principal.user_id
    row.reviewed_at = now
    row.review_comment = body.comment.strip() if body.comment else None
    if decision == CorrectionStatus.APPROVED.value:
        check_out_at = row.proposed_check_out_at
        if check_out_at is None:
            check_out_at = session_row.check_out_at
        try:
            if check_out_at is not None:
                can_check_out(
                    check_in_at=row.proposed_check_in_at,
                    check_out_at=check_out_at,
                )
            elif session_row.status != AttendanceStatus.OPEN.value:
                other_open = await _open_session(db, session_row.employee_id, lock=True)
                if other_open is not None and other_open.id != session_row.id:
                    raise AttendanceError("An open attendance session already exists.")
        except AttendanceError as exc:
            _raise_attendance(exc, conflict="open attendance session" in str(exc).lower())
        await _apply_times(
            db,
            session_row,
            organization_id=principal.organization_id,
            check_in_at=row.proposed_check_in_at,
            check_out_at=check_out_at,
        )
    after = _punch_snapshot(session_row)
    db.add(
        AuditEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            entity_type="attendance_correction",
            entity_id=str(row.id),
            action=(
                "attendance.correction.approve"
                if decision == CorrectionStatus.APPROVED.value
                else "attendance.correction.reject"
            ),
            before_json=before,
            after_json=after,
        )
    )
    await db.commit()
    await db.refresh(row)
    return _correction_out(row)
