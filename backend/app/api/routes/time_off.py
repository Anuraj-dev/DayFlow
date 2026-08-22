from fastapi import APIRouter, Depends

from app.api.deps import CurrentPrincipal, get_current_principal

router = APIRouter(prefix="/time-off", tags=["time-off"])


@router.get("")
async def time_off_home(principal: CurrentPrincipal = Depends(get_current_principal)) -> dict:
    return {
        "role": principal.role.value,
        "employee_id": str(principal.employee_id) if principal.employee_id else None,
        "balances": [],
        "requests": [],
        "pending_queue": [],
    }
