from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_current_principal
from app.core.db import get_db
from app.domain.roles import Role
from app.models import PayrollPeriod, PayrollRecord

router = APIRouter(prefix="/payroll", tags=["payroll"])


@router.get("")
async def payroll_home(
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    periods = list(
        await db.scalars(
            select(PayrollPeriod)
            .where(PayrollPeriod.organization_id == principal.organization_id)
            .order_by(PayrollPeriod.starts_on.desc())
        )
    )
    records_query = select(PayrollRecord).join(PayrollPeriod).where(
        PayrollPeriod.organization_id == principal.organization_id
    )
    if principal.role is Role.EMPLOYEE:
        if principal.employee_id is None:
            records_query = records_query.where(False)
        else:
            records_query = records_query.where(
                PayrollRecord.employee_id == principal.employee_id,
                PayrollRecord.published_at.is_not(None),
            )
    records = list(await db.scalars(records_query))
    return {
        "role": principal.role.value,
        "periods": [
            {
                "id": str(period.id),
                "starts_on": period.starts_on.isoformat(),
                "ends_on": period.ends_on.isoformat(),
                "pay_date": period.pay_date.isoformat(),
                "status": period.status,
            }
            for period in periods
        ],
        "records": [
            {
                "id": str(record.id),
                "employee_id": str(record.employee_id),
                "net_amount": str(record.net_amount),
                "currency": record.currency,
                "published_at": record.published_at.isoformat() if record.published_at else None,
            }
            for record in records
        ],
    }
