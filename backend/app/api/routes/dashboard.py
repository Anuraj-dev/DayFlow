from fastapi import APIRouter, Depends

from app.api.deps import CurrentPrincipal, get_current_principal
from app.domain.roles import Role

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard(principal: CurrentPrincipal = Depends(get_current_principal)) -> dict:
    if principal.role is Role.HR:
        return {
            "kind": "HR",
            "headline": "Today's coverage",
            "headcount": 2,
            "pending_approvals": 0,
            "attendance_exceptions": 0,
            "payroll_period_due": False,
        }
    return {
        "kind": "EMPLOYEE",
        "headline": "Check in when the workday starts",
        "attendance_state": "not_checked_in",
        "leave_balances": [],
        "next_pay_date": "2026-09-05",
        "incomplete_profile": False,
    }
