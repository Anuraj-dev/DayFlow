import secrets
from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentPrincipal, get_current_principal, require_hr
from app.core.db import get_db
from app.domain.attendance import derive_presence
from app.domain.identity import (
    IdentityError,
    assert_employee_patch_allowed,
    build_employee_code,
    can_edit_employee,
    can_read_employee,
    hash_invite_token,
    normalize_email,
)
from app.domain.leave import LeaveRequestStatus
from app.domain.roles import EmployeeStatus, Role, UserStatus
from app.models import (
    AccountInvite,
    AttendanceSession,
    AuditEvent,
    Employee,
    JobAssignment,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    Organization,
    OrganizationMembership,
    User,
)
from app.schemas.employee import (
    EmployeeCreateRequest,
    EmployeeHireResponse,
    EmployeeSummary,
    EmployeeUpdateRequest,
)

router = APIRouter(prefix="/employees", tags=["employees"])

_JOB_FIELDS = frozenset({"title", "department", "employment_type", "location"})
_EMPLOYEE_FIELDS = frozenset({"phone", "address", "first_name", "last_name", "status"})
_REQUIRED_PATCH_FIELDS = frozenset(
    {"first_name", "last_name", "status", "title", "department", "employment_type", "location"}
)


def _summary(
    employee: Employee,
    email: str | None = None,
    role: str | None = None,
    presence: str | None = None,
) -> EmployeeSummary:
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
        presence=presence,
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
    presence = await _presence_by_employee(db, employees, organization_id)
    out: list[EmployeeSummary] = []
    for employee in employees:
        user = users_by_id.get(employee.user_id) if employee.user_id else None
        membership = memberships_by_user.get(employee.user_id) if employee.user_id else None
        out.append(
            _summary(
                employee,
                user.email if user else None,
                membership.role if membership else None,
                presence.get(employee.id),
            )
        )
    return out


async def _presence_by_employee(
    db: AsyncSession, employees: list[Employee], organization_id: UUID
) -> dict[UUID, str]:
    if not employees:
        return {}
    org = await db.get(Organization, organization_id)
    timezone_name = org.timezone if org and org.timezone else "UTC"
    today = datetime.now(UTC).astimezone(ZoneInfo(timezone_name)).date()
    ids = [employee.id for employee in employees]
    on_leave_ids = set(
        await db.scalars(
            select(LeaveRequest.employee_id).where(
                LeaveRequest.employee_id.in_(ids),
                LeaveRequest.status == LeaveRequestStatus.APPROVED.value,
                LeaveRequest.starts_on <= today,
                LeaveRequest.ends_on >= today,
            )
        )
    )
    present_ids = set(
        await db.scalars(
            select(AttendanceSession.employee_id).where(
                AttendanceSession.employee_id.in_(ids),
                AttendanceSession.work_date == today,
                AttendanceSession.check_in_at.is_not(None),
            )
        )
    )
    return {
        employee.id: derive_presence(
            invited=employee.status == EmployeeStatus.INVITED.value,
            on_leave=employee.id in on_leave_ids,
            present_today=employee.id in present_ids,
        )
        for employee in employees
    }


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


@router.post("", response_model=EmployeeHireResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    body: EmployeeCreateRequest,
    principal: CurrentPrincipal = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
) -> EmployeeHireResponse:
    email = normalize_email(str(body.email))
    existing = await db.scalar(select(User).where(func.lower(User.email) == email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This email is already in use.")
    invited_email = await db.scalar(
        select(AccountInvite.id).where(
            AccountInvite.organization_id == principal.organization_id,
            func.lower(AccountInvite.email) == email,
            AccountInvite.accepted_at.is_(None),
        )
    )
    if invited_email is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This email is already in use.")

    joined_on = body.joined_on or datetime.now(UTC).date()
    year = joined_on.year
    serial = (
        await db.scalar(
            select(func.count()).select_from(Employee).where(
                Employee.organization_id == principal.organization_id,
                Employee.joined_on >= date(year, 1, 1),
                Employee.joined_on <= date(year, 12, 31),
            )
        )
        or 0
    ) + 1
    employee_code = build_employee_code(
        first_name=body.first_name,
        last_name=body.last_name,
        year=year,
        serial=serial,
    )
    while await db.scalar(
        select(Employee.id).where(
            Employee.organization_id == principal.organization_id,
            Employee.employee_code == employee_code,
        )
    ):
        serial += 1
        employee_code = build_employee_code(
            first_name=body.first_name,
            last_name=body.last_name,
            year=year,
            serial=serial,
        )

    employee = Employee(
        organization_id=principal.organization_id,
        employee_code=employee_code,
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        status=EmployeeStatus.INVITED.value,
        joined_on=joined_on,
    )
    db.add(employee)
    await db.flush()
    db.add(
        JobAssignment(
            employee_id=employee.id,
            title=(body.title or "Employee").strip(),
            department=(body.department or "General").strip(),
            employment_type="FULL_TIME",
            location=(body.location or "Office").strip(),
            starts_on=joined_on,
        )
    )
    types = list(
        await db.scalars(
            select(LeaveType).where(LeaveType.organization_id == principal.organization_id, LeaveType.active.is_(True))
        )
    )
    year_start, year_end = date(year, 1, 1), date(year, 12, 31)
    grants = {"PAID": 18.0, "SICK": 8.0, "UNPAID": 0.0}
    for leave_type in types:
        db.add(
            LeaveBalance(
                employee_id=employee.id,
                leave_type_id=leave_type.id,
                period_start=year_start,
                period_end=year_end,
                granted_days=grants.get(leave_type.code.upper(), 0.0),
            )
        )
    invite_token = secrets.token_urlsafe(16)
    db.add(
        AccountInvite(
            organization_id=principal.organization_id,
            employee_id=employee.id,
            email=email,
            role=Role.EMPLOYEE.value,
            token_hash=hash_invite_token(invite_token),
            expires_at=datetime.now(UTC) + timedelta(days=7),
            created_by=principal.user_id,
        )
    )
    db.add(
        AuditEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            entity_type="employee",
            entity_id=str(employee.id),
            action="employee.create",
            before_json=None,
            after_json={"employee_code": employee_code, "email": email},
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create this employee.",
        ) from exc
    employee = await db.scalar(
        select(Employee)
        .where(Employee.id == employee.id)
        .options(selectinload(Employee.job_assignments))
    )
    assert employee is not None
    summary = (await _summaries(db, [employee], principal.organization_id))[0]
    return EmployeeHireResponse(
        employee=summary,
        invite_token=invite_token,
        employee_code=employee_code,
        detail="Share the employee code and invite token so they can activate.",
    )


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
