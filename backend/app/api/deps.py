from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_access_token
from app.domain.roles import Role
from app.models import Employee, OrganizationMembership, User

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentPrincipal:
    user_id: UUID
    organization_id: UUID
    role: Role
    email: str
    employee_id: UUID | None
    user: User
    employee: Employee | None


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> CurrentPrincipal:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not signed in.")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
        organization_id = UUID(payload["org"])
        role = Role(payload["role"])
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session."
        ) from exc

    user = await db.get(User, user_id)
    if user is None or user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is not active.")

    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No membership in this organization.")

    employee = await db.scalar(
        select(Employee).where(
            Employee.user_id == user_id,
            Employee.organization_id == organization_id,
        )
    )
    return CurrentPrincipal(
        user_id=user.id,
        organization_id=organization_id,
        role=Role(membership.role),
        email=user.email,
        employee_id=employee.id if employee else None,
        user=user,
        employee=employee,
    )


def require_hr(principal: CurrentPrincipal = Depends(get_current_principal)) -> CurrentPrincipal:
    if principal.role is not Role.HR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HR role required.")
    return principal
