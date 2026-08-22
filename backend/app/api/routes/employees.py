from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentPrincipal, get_current_principal, require_hr
from app.core.db import get_db
from app.domain.identity import can_read_employee
from app.models import Employee, OrganizationMembership, User
from app.schemas.employee import EmployeeSummary

router = APIRouter(prefix="/employees", tags=["employees"])


def _summary(employee: Employee, email: str | None = None, role: str | None = None) -> EmployeeSummary:
    current_job = next((job for job in employee.job_assignments if job.ends_on is None), None)
    return EmployeeSummary(
        id=employee.id,
        employee_code=employee.employee_code,
        first_name=employee.first_name,
        last_name=employee.last_name,
        status=employee.status,
        email=email,
        role=role,
        department=current_job.department if current_job else None,
        title=current_job.title if current_job else None,
        joined_on=employee.joined_on,
    )


@router.get("", response_model=list[EmployeeSummary])
async def list_employees(
    principal: CurrentPrincipal = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
) -> list[EmployeeSummary]:
    result = await db.scalars(
        select(Employee)
        .where(Employee.organization_id == principal.organization_id)
        .options(selectinload(Employee.job_assignments))
        .order_by(Employee.employee_code)
    )
    employees = list(result)
    summaries: list[EmployeeSummary] = []
    for employee in employees:
        email = None
        role = None
        if employee.user_id:
            user = await db.get(User, employee.user_id)
            membership = await db.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.user_id == employee.user_id,
                    OrganizationMembership.organization_id == principal.organization_id,
                )
            )
            email = user.email if user else None
            role = membership.role if membership else None
        summaries.append(_summary(employee, email, role))
    return summaries


@router.get("/{employee_id}", response_model=EmployeeSummary)
async def get_employee(
    employee_id: UUID,
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> EmployeeSummary:
    employee = await db.scalar(
        select(Employee)
        .where(
            Employee.id == employee_id,
            Employee.organization_id == principal.organization_id,
        )
        .options(selectinload(Employee.job_assignments))
    )
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")
    if not can_read_employee(
        role=principal.role,
        actor_employee_id=principal.employee_id,
        target_employee_id=employee.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employees can read only their own record.",
        )
    return _summary(employee)
