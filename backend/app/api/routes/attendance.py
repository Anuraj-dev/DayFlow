from fastapi import APIRouter, Depends

from app.api.deps import CurrentPrincipal, get_current_principal

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("")
async def attendance_home(principal: CurrentPrincipal = Depends(get_current_principal)) -> dict:
    return {
        "role": principal.role.value,
        "employee_id": str(principal.employee_id) if principal.employee_id else None,
        "sessions": [],
        "open_session": None,
        "exceptions": [],
    }
