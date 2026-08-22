from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_current_principal, require_hr
from app.core.db import get_db
from app.domain.leave import (
    LeaveError,
    LeaveRequestStatus,
    assert_can_cancel,
    assert_can_review,
    assert_can_submit,
    counted_days,
    remaining_balance,
)
from app.domain.roles import Role
from app.models import (
    AuditEvent,
    Employee,
    Holiday,
    LeaveBalance,
    LeaveRequest,
    LeaveRequestEvent,
    LeaveType,
    WorkPolicy,
)
from app.schemas.time_off import (
    LeaveBalanceOut,
    LeaveDecisionRequest,
    LeaveRequestCreate,
    LeaveRequestOut,
    TimeOffHome,
)

router = APIRouter(prefix="/time-off", tags=["time-off"])

_BLOCKING_STATUSES = (LeaveRequestStatus.PENDING.value, LeaveRequestStatus.APPROVED.value)


def _raise_leave(exc: LeaveError, *, conflict: bool = False) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT if conflict else status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    ) from exc


def _require_employee(principal: CurrentPrincipal) -> None:
    if principal.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An employee record is required for time off.",
        )


async def _work_context(db: AsyncSession, organization_id: UUID) -> tuple[set[int], set]:
    policy = await db.scalar(select(WorkPolicy).where(WorkPolicy.organization_id == organization_id))
    workweek = set(policy.workweek) if policy and policy.workweek else {0, 1, 2, 3, 4}
    weekend_weekdays = set(range(7)) - workweek
    holidays = set(
        await db.scalars(select(Holiday.date).where(Holiday.organization_id == organization_id))
    )
    return weekend_weekdays, holidays


async def _leave_type(db: AsyncSession, organization_id: UUID, leave_type: str) -> LeaveType:
    query = select(LeaveType).where(LeaveType.organization_id == organization_id, LeaveType.active.is_(True))
    try:
        type_id = UUID(leave_type)
        query = query.where(LeaveType.id == type_id)
    except ValueError:
        query = query.where(LeaveType.code == leave_type.strip().upper())
    row = await db.scalar(query)
    if row is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown leave type.")
    return row


async def _balance_for(
    db: AsyncSession, employee_id: UUID, leave_type_id: UUID, on_date
) -> LeaveBalance | None:
    return await db.scalar(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.leave_type_id == leave_type_id,
            LeaveBalance.period_start <= on_date,
            LeaveBalance.period_end >= on_date,
        )
    )


async def _overlaps(
    db: AsyncSession, employee_id: UUID, starts_on, ends_on, *, exclude_id: UUID | None = None
) -> bool:
    query = select(LeaveRequest).where(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_(_BLOCKING_STATUSES),
        LeaveRequest.starts_on <= ends_on,
        LeaveRequest.ends_on >= starts_on,
    )
    if exclude_id is not None:
        query = query.where(LeaveRequest.id != exclude_id)
    existing = await db.scalar(query)
    return existing is not None


async def _pending_counted(db: AsyncSession, employee_id: UUID, leave_type_id: UUID) -> float:
    rows = list(
        await db.scalars(
            select(LeaveRequest).where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.leave_type_id == leave_type_id,
                LeaveRequest.status == LeaveRequestStatus.PENDING.value,
            )
        )
    )
    return sum(row.counted_days for row in rows)


def _request_out(row: LeaveRequest, leave_type_code: str, employee_name: str | None = None) -> LeaveRequestOut:
    return LeaveRequestOut(
        id=row.id,
        employee_id=row.employee_id,
        leave_type=leave_type_code,
        starts_on=row.starts_on,
        ends_on=row.ends_on,
        counted_days=row.counted_days,
        reason=row.reason,
        status=row.status,
        employee_name=employee_name,
        review_comment=row.review_comment,
        submitted_at=row.submitted_at,
    )


@router.get("", response_model=TimeOffHome)
async def time_off_home(
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TimeOffHome:
    types = list(
        await db.scalars(select(LeaveType).where(LeaveType.organization_id == principal.organization_id))
    )
    type_by_id = {row.id: row for row in types}

    request_query = (
        select(LeaveRequest, Employee)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .where(Employee.organization_id == principal.organization_id)
        .order_by(LeaveRequest.submitted_at.desc())
    )
    if principal.role is not Role.HR:
        _require_employee(principal)
        request_query = request_query.where(LeaveRequest.employee_id == principal.employee_id)
    request_rows = (await db.execute(request_query)).all()

    balances: list[LeaveBalanceOut] = []
    if principal.employee_id is not None:
        balance_rows = list(
            await db.scalars(select(LeaveBalance).where(LeaveBalance.employee_id == principal.employee_id))
        )
        for row in balance_rows:
            leave_type = type_by_id.get(row.leave_type_id)
            if leave_type is None:
                continue
            balances.append(
                LeaveBalanceOut(
                    leave_type=leave_type.code,
                    remaining_days=remaining_balance(
                        granted=row.granted_days, used=row.used_days, adjustment=row.adjustment_days
                    ),
                    granted_days=row.granted_days,
                    used_days=row.used_days,
                )
            )

    requests = [
        _request_out(row, type_by_id[row.leave_type_id].code, f"{person.first_name} {person.last_name}")
        for row, person in request_rows
        if row.leave_type_id in type_by_id
    ]
    pending_queue: list[LeaveRequestOut] = []
    if principal.role is Role.HR:
        pending_queue = [row for row in requests if row.status == LeaveRequestStatus.PENDING.value]
        if principal.employee_id is None:
            requests = []

    return TimeOffHome(
        role=principal.role.value,
        employee_id=principal.employee_id,
        balances=balances,
        requests=requests,
        pending_queue=pending_queue,
    )


@router.post("/requests", response_model=LeaveRequestOut)
async def create_leave_request(
    body: LeaveRequestCreate,
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> LeaveRequestOut:
    _require_employee(principal)
    if not body.reason.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A reason is required.")
    leave_type = await _leave_type(db, principal.organization_id, body.leave_type)
    weekend_weekdays, holidays = await _work_context(db, principal.organization_id)
    try:
        counted = counted_days(
            body.starts_on,
            body.ends_on,
            weekend_weekdays=weekend_weekdays,
            holidays=holidays,
        )
    except LeaveError as exc:
        _raise_leave(exc)

    balance = await _balance_for(db, principal.employee_id, leave_type.id, body.starts_on)
    remaining = 0.0
    if balance is not None:
        remaining = remaining_balance(
            granted=balance.granted_days, used=balance.used_days, adjustment=balance.adjustment_days
        )
        remaining -= await _pending_counted(db, principal.employee_id, leave_type.id)
    overlaps = await _overlaps(db, principal.employee_id, body.starts_on, body.ends_on)
    try:
        assert_can_submit(
            counted=counted,
            remaining=remaining,
            requires_balance=leave_type.requires_balance,
            overlaps_existing=overlaps,
        )
    except LeaveError as exc:
        _raise_leave(exc, conflict="overlap" in str(exc).lower())

    row = LeaveRequest(
        employee_id=principal.employee_id,
        leave_type_id=leave_type.id,
        starts_on=body.starts_on,
        ends_on=body.ends_on,
        counted_days=counted,
        reason=body.reason.strip(),
        status=LeaveRequestStatus.PENDING.value,
        submitted_at=datetime.now(UTC),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _request_out(row, leave_type.code)


async def _org_request(db: AsyncSession, organization_id: UUID, request_id: UUID) -> LeaveRequest:
    row = await db.scalar(
        select(LeaveRequest)
        .join(Employee, Employee.id == LeaveRequest.employee_id)
        .where(
            LeaveRequest.id == request_id,
            Employee.organization_id == organization_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found.")
    return row


async def _leave_type_code(db: AsyncSession, leave_type_id: UUID) -> str:
    leave_type = await db.get(LeaveType, leave_type_id)
    if leave_type is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown leave type.")
    return leave_type.code


@router.post("/requests/{request_id}/cancel", response_model=LeaveRequestOut)
async def cancel_leave_request(
    request_id: UUID,
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> LeaveRequestOut:
    _require_employee(principal)
    row = await _org_request(db, principal.organization_id, request_id)
    try:
        assert_can_cancel(current_status=row.status, is_owner=row.employee_id == principal.employee_id)
    except LeaveError as exc:
        forbidden = "only their own" in str(exc)
        if forbidden:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        _raise_leave(exc)
    db.add(
        LeaveRequestEvent(
            leave_request_id=row.id,
            actor_user_id=principal.user_id,
            from_status=row.status,
            to_status=LeaveRequestStatus.CANCELLED.value,
        )
    )
    row.status = LeaveRequestStatus.CANCELLED.value
    await db.commit()
    await db.refresh(row)
    return _request_out(row, await _leave_type_code(db, row.leave_type_id))


def _used_days(balance: LeaveBalance | None) -> float:
    return balance.used_days if balance is not None else 0.0


def _decision_snapshot(row: LeaveRequest, *, used_days: float) -> dict:
    return {
        "status": row.status,
        "used_days": used_days,
        "counted_days": row.counted_days,
        "employee_id": str(row.employee_id),
        "leave_type_id": str(row.leave_type_id),
    }


@router.post("/requests/{request_id}/approve", response_model=LeaveRequestOut)
async def approve_leave_request(
    request_id: UUID,
    body: LeaveDecisionRequest,
    principal: CurrentPrincipal = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
) -> LeaveRequestOut:
    row = await _org_request(db, principal.organization_id, request_id)
    try:
        assert_can_review(current_status=row.status, decision=LeaveRequestStatus.APPROVED.value, comment=body.comment)
    except LeaveError as exc:
        _raise_leave(exc)
    leave_type = await db.get(LeaveType, row.leave_type_id)
    if leave_type is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown leave type.")
    balance = await _balance_for(db, row.employee_id, row.leave_type_id, row.starts_on)
    remaining = 0.0
    if balance is not None:
        remaining = remaining_balance(
            granted=balance.granted_days, used=balance.used_days, adjustment=balance.adjustment_days
        )
    if leave_type.requires_balance and row.counted_days > remaining:
        _raise_leave(LeaveError("Insufficient leave balance."))
    before = _decision_snapshot(row, used_days=_used_days(balance))
    comment = body.comment.strip() if body.comment else None
    now = datetime.now(UTC)
    if balance is not None:
        balance.used_days = balance.used_days + row.counted_days
    row.status = LeaveRequestStatus.APPROVED.value
    row.reviewed_by = principal.user_id
    row.reviewed_at = now
    row.review_comment = comment
    db.add(
        LeaveRequestEvent(
            leave_request_id=row.id,
            actor_user_id=principal.user_id,
            from_status=LeaveRequestStatus.PENDING.value,
            to_status=LeaveRequestStatus.APPROVED.value,
            comment=comment,
        )
    )
    db.add(
        AuditEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            entity_type="leave_request",
            entity_id=str(row.id),
            action="leave.request.approve",
            before_json=before,
            after_json=_decision_snapshot(row, used_days=_used_days(balance)),
        )
    )
    await db.commit()
    await db.refresh(row)
    return _request_out(row, leave_type.code)


@router.post("/requests/{request_id}/reject", response_model=LeaveRequestOut)
async def reject_leave_request(
    request_id: UUID,
    body: LeaveDecisionRequest,
    principal: CurrentPrincipal = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
) -> LeaveRequestOut:
    row = await _org_request(db, principal.organization_id, request_id)
    try:
        assert_can_review(
            current_status=row.status,
            decision=LeaveRequestStatus.REJECTED.value,
            comment=body.comment,
        )
    except LeaveError as exc:
        _raise_leave(exc)
    leave_type = await db.get(LeaveType, row.leave_type_id)
    if leave_type is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown leave type.")
    balance = await _balance_for(db, row.employee_id, row.leave_type_id, row.starts_on)
    before = _decision_snapshot(row, used_days=_used_days(balance))
    comment = body.comment.strip() if body.comment else None
    row.status = LeaveRequestStatus.REJECTED.value
    row.reviewed_by = principal.user_id
    row.reviewed_at = datetime.now(UTC)
    row.review_comment = comment
    db.add(
        LeaveRequestEvent(
            leave_request_id=row.id,
            actor_user_id=principal.user_id,
            from_status=LeaveRequestStatus.PENDING.value,
            to_status=LeaveRequestStatus.REJECTED.value,
            comment=comment,
        )
    )
    db.add(
        AuditEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            entity_type="leave_request",
            entity_id=str(row.id),
            action="leave.request.reject",
            before_json=before,
            after_json=_decision_snapshot(row, used_days=_used_days(balance)),
        )
    )
    await db.commit()
    await db.refresh(row)
    return _request_out(row, leave_type.code)
