from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_current_principal
from app.core.db import get_db
from app.domain.attendance import AttendanceStatus, CorrectionStatus
from app.domain.leave import LeaveRequestStatus, remaining_balance
from app.domain.payroll import PayrollPeriodStatus
from app.domain.roles import Role
from app.models import (
    AttendanceCorrectionRequest,
    AttendanceSession,
    Employee,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    Organization,
    PayrollPeriod,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_EMPLOYEE_HEADLINES = {
    "on_leave": "On approved leave today",
    "checked_in": "You are checked in",
    "checked_out": "Workday closed",
    "not_checked_in": "Check in when the workday starts",
}


async def _org_today(db: AsyncSession, organization_id) -> date:
    org = await db.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    timezone_name = org.timezone or "UTC"
    return datetime.now(UTC).astimezone(ZoneInfo(timezone_name)).date()


@router.get("")
async def dashboard(
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    today = await _org_today(db, principal.organization_id)
    if principal.role is Role.HR:
        headcount = await db.scalar(
            select(func.count()).select_from(Employee).where(
                Employee.organization_id == principal.organization_id
            )
        )
        pending_approvals = await db.scalar(
            select(func.count())
            .select_from(LeaveRequest)
            .join(Employee, Employee.id == LeaveRequest.employee_id)
            .where(
                Employee.organization_id == principal.organization_id,
                LeaveRequest.status == LeaveRequestStatus.PENDING.value,
            )
        )
        pending_corrections = await db.scalar(
            select(func.count())
            .select_from(AttendanceCorrectionRequest)
            .join(
                AttendanceSession,
                AttendanceSession.id == AttendanceCorrectionRequest.attendance_session_id,
            )
            .join(Employee, Employee.id == AttendanceSession.employee_id)
            .where(
                Employee.organization_id == principal.organization_id,
                AttendanceCorrectionRequest.status == CorrectionStatus.PENDING.value,
            )
        )
        missing_checkouts = await db.scalar(
            select(func.count())
            .select_from(AttendanceSession)
            .join(Employee, Employee.id == AttendanceSession.employee_id)
            .where(
                Employee.organization_id == principal.organization_id,
                AttendanceSession.status == AttendanceStatus.OPEN.value,
                AttendanceSession.check_out_at.is_(None),
            )
        )
        due = await db.scalar(
            select(PayrollPeriod.id).where(
                PayrollPeriod.organization_id == principal.organization_id,
                PayrollPeriod.status == PayrollPeriodStatus.DRAFT.value,
                PayrollPeriod.ends_on <= today,
            )
        )
        return {
            "kind": "HR",
            "headline": "Today's coverage",
            "headcount": int(headcount or 0),
            "pending_approvals": int(pending_approvals or 0),
            "attendance_exceptions": int(pending_corrections or 0) + int(missing_checkouts or 0),
            "payroll_period_due": due is not None,
        }

    attendance_state = "not_checked_in"
    if principal.employee_id is not None:
        on_leave = await db.scalar(
            select(LeaveRequest.id).where(
                LeaveRequest.employee_id == principal.employee_id,
                LeaveRequest.status == LeaveRequestStatus.APPROVED.value,
                LeaveRequest.starts_on <= today,
                LeaveRequest.ends_on >= today,
            )
        )
        open_session = await db.scalar(
            select(AttendanceSession.id).where(
                AttendanceSession.employee_id == principal.employee_id,
                AttendanceSession.status == AttendanceStatus.OPEN.value,
                AttendanceSession.check_out_at.is_(None),
            )
        )
        closed_today = await db.scalar(
            select(AttendanceSession.id).where(
                AttendanceSession.employee_id == principal.employee_id,
                AttendanceSession.work_date == today,
                AttendanceSession.check_out_at.is_not(None),
            )
        )
        if on_leave is not None:
            attendance_state = "on_leave"
        elif open_session is not None:
            attendance_state = "checked_in"
        elif closed_today is not None:
            attendance_state = "checked_out"

    leave_balances: list[dict] = []
    if principal.employee_id is not None:
        rows = (
            await db.execute(
                select(LeaveBalance, LeaveType)
                .join(LeaveType, LeaveType.id == LeaveBalance.leave_type_id)
                .where(
                    LeaveBalance.employee_id == principal.employee_id,
                    LeaveType.organization_id == principal.organization_id,
                    LeaveBalance.period_start <= today,
                    LeaveBalance.period_end >= today,
                )
                .order_by(LeaveType.code)
            )
        ).all()
        for balance, leave_type in rows:
            remaining = remaining_balance(
                granted=balance.granted_days,
                used=balance.used_days,
                adjustment=balance.adjustment_days,
            )
            leave_balances.append(
                {
                    "leave_type": leave_type.code,
                    "remaining_days": remaining,
                }
            )

    next_pay = await db.scalar(
        select(func.min(PayrollPeriod.pay_date)).where(
            PayrollPeriod.organization_id == principal.organization_id,
            PayrollPeriod.pay_date >= today,
        )
    )
    employee = principal.employee
    incomplete_profile = employee is None or not (employee.phone and employee.address)
    return {
        "kind": "EMPLOYEE",
        "headline": _EMPLOYEE_HEADLINES[attendance_state],
        "attendance_state": attendance_state,
        "leave_balances": leave_balances,
        "next_pay_date": next_pay.isoformat() if next_pay else None,
        "incomplete_profile": incomplete_profile,
    }
