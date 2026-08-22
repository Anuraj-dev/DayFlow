from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentPrincipal, get_current_principal
from app.core.db import get_db
from app.domain.identity import (
    IdentityError,
    assert_employee_patch_allowed,
    can_edit_employee,
    can_read_employee,
)
from app.domain.roles import EmployeeStatus, UserStatus
from app.models import AuditEvent, Employee, OrganizationMembership, User
from app.schemas.employee import EmployeeSummary, EmployeeUpdateRequest

router = APIRouter(prefix="/employees", tags=["employees"])

_JOB_FIELDS = frozenset({"title", "department", "employment_type", "location"})
_EMPLOYEE_FIELDS = frozenset({"phone", "address", "first_name", "last_name", "status"})
_REQUIRED_PATCH_FIELDS = frozenset(
    {"first_name", "last_name", "status", "title", "department", "employment_type", "location"}
)


def _summary(employee: Employee, email: str | None = None, role: str | None = None) -> EmployeeSummary:
    current_job = next((job for job in employee.job_assignments if job.ends_on is None), None)
    return EmployeeSummary(
        id=employee.id,
        employee_code=employee.employee_code,
        first_name=employee.first_name,
        last_name=employee.last_name,
        status=employee.status,
        phone=employee.phone,
        address=employee.address,
        email=email,
        role=role,
        department=current_job.department if current_job else None,
        title=current_job.title if current_job else None,
        employment_type=current_job.employment_type if current_job else None,
        location=current_job.location if current_job else None,
        joined_on=employee.joined_on,
    )


def _snapshot(employee: Employee) -> dict:
    summary = _summary(employee)
    return summary.model_dump(mode="json")


async def _summaries(
    db: AsyncSession, employees: list[Employee], organization_id: UUID
) -> list[EmployeeSummary]:
    user_ids = [employee.user_id for employee in employees if employee.user_id]
    users_by_id: dict[UUID, User] = {}
    memberships_by_user: dict[UUID, OrganizationMembership] = {}
    if user_ids:
        users_by_id = {
            user.id: user
            for user in (await db.scalars(select(User).where(User.id.in_(user_ids)))).all()
        }
        memberships_by_user = {
            membership.user_id: membership
            for membership in (
                await db.scalars(
                    select(OrganizationMembership).where(
                        OrganizationMembership.organization_id == organization_id,
                        OrganizationMembership.user_id.in_(user_ids),
                    )
                )
            ).all()
        }
    out: list[EmployeeSummary] = []
    for employee in employees:
        user = users_by_id.get(employee.user_id) if employee.user_id else None
        membership = memberships_by_user.get(employee.user_id) if employee.user_id else None
        out.append(
            _summary(
                employee,
                user.email if user else None,
                membership.role if membership else None,
            )
        )
    return out


@router.get("", response_model=list[EmployeeSummary])
async def list_employees(
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> list[EmployeeSummary]:
    result = await db.scalars(
        select(Employee)
        .where(Employee.organization_id == principal.organization_id)
        .options(selectinload(Employee.job_assignments))
        .order_by(Employee.employee_code)
    )
    return await _summaries(db, list(result), principal.organization_id)


@router.get("/{employee_id}", response_model=EmployeeSummary)
async def get_employee(
    employee_id: UUID,
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> EmployeeSummary:
    if not can_read_employee(
        role=principal.role,
        actor_employee_id=principal.employee_id,
        target_employee_id=employee_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to read this employee.",
        )
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
    return (await _summaries(db, [employee], principal.organization_id))[0]


@router.patch("/{employee_id}", response_model=EmployeeSummary)
async def patch_employee(
    employee_id: UUID,
    body: EmployeeUpdateRequest,
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> EmployeeSummary:
    if not can_edit_employee(
        role=principal.role,
        actor_employee_id=principal.employee_id,
        target_employee_id=employee_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employees can edit only their own record.",
        )

    updates = body.model_dump(exclude_unset=True, mode="json")
    try:
        assert_employee_patch_allowed(role=principal.role, fields=set(updates))
    except IdentityError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    for field, value in updates.items():
        if field in _REQUIRED_PATCH_FIELDS and (value is None or value == ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field} cannot be empty.",
            )

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

    before = _snapshot(employee)

    for field in _EMPLOYEE_FIELDS:
        if field in updates:
            setattr(employee, field, updates[field])

    job_updates = {field: updates[field] for field in _JOB_FIELDS if field in updates}
    if job_updates:
        current_job = next((job for job in employee.job_assignments if job.ends_on is None), None)
        if current_job is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active job assignment to update.",
            )
        for field, value in job_updates.items():
            setattr(current_job, field, value)

    if "status" in updates and employee.user_id is not None:
        linked_user = await db.get(User, employee.user_id)
        if linked_user is not None:
            if updates["status"] == EmployeeStatus.INACTIVE.value:
                linked_user.status = UserStatus.DISABLED.value
            elif updates["status"] == EmployeeStatus.ACTIVE.value:
                linked_user.status = UserStatus.ACTIVE.value

    after = _snapshot(employee)
    db.add(
        AuditEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            entity_type="employee",
            entity_id=str(employee.id),
            action="employee.update",
            before_json=before,
            after_json=after,
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee update could not be saved.",
        ) from exc
    await db.refresh(employee)
    # Refresh job assignments after commit
    employee = await db.scalar(
        select(Employee)
        .where(Employee.id == employee.id)
        .options(selectinload(Employee.job_assignments))
    )
    assert employee is not None
    return (await _summaries(db, [employee], principal.organization_id))[0]
