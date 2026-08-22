from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email import EmailMessage, email_adapter
from app.api.deps import CurrentPrincipal, get_current_principal
from app.core.db import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.identity import IdentityError, assert_invite_usable, hash_invite_token, role_from_invite
from app.domain.roles import EmployeeStatus, Role, UserStatus
from app.models import AccountInvite, Employee, OrganizationMembership, User
from app.schemas.auth import (
    ActivateAccountRequest,
    ActivateAccountResponse,
    SessionUser,
    SignInRequest,
    SignInResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _session_user(
    db: AsyncSession, user: User, membership: OrganizationMembership
) -> SessionUser:
    employee = await db.scalar(
        select(Employee).where(
            Employee.user_id == user.id,
            Employee.organization_id == membership.organization_id,
        )
    )
    return SessionUser(
        id=user.id,
        email=user.email,
        role=Role(membership.role),
        organization_id=membership.organization_id,
        employee_id=employee.id if employee else None,
        first_name=employee.first_name if employee else None,
        last_name=employee.last_name if employee else None,
        employee_code=employee.employee_code if employee else None,
    )


@router.post("/sign-in", response_model=SignInResponse)
async def sign_in(body: SignInRequest, db: AsyncSession = Depends(get_db)) -> SignInResponse:
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials.")
    if user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is locked or disabled.")

    membership = await db.scalar(
        select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization membership.")

    user.last_login_at = datetime.now(UTC)
    await db.commit()

    session_user = await _session_user(db, user, membership)
    token = create_access_token(
        user_id=user.id,
        organization_id=membership.organization_id,
        role=Role(membership.role),
        email=user.email,
    )
    return SignInResponse(access_token=token, user=session_user)


@router.post("/activate-account", response_model=ActivateAccountResponse)
async def activate_account(
    body: ActivateAccountRequest, db: AsyncSession = Depends(get_db)
) -> ActivateAccountResponse:
    employee = await db.scalar(select(Employee).where(Employee.employee_code == body.employee_code))
    invite = None
    if employee is not None:
        invite = await db.scalar(
            select(AccountInvite).where(
                AccountInvite.employee_id == employee.id,
                AccountInvite.organization_id == employee.organization_id,
                AccountInvite.email == body.email,
                AccountInvite.token_hash == hash_invite_token(body.token),
            )
        )
    if employee is None or invite is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite is invalid.")

    now = datetime.now(UTC)
    try:
        assert_invite_usable(accepted_at=invite.accepted_at, expires_at=invite.expires_at, now=now)
    except IdentityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    role = role_from_invite(invite.role)
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        email_verified_at=now,
        status=UserStatus.ACTIVE.value,
    )
    db.add(user)
    await db.flush()
    db.add(
        OrganizationMembership(
            organization_id=invite.organization_id,
            user_id=user.id,
            role=role.value,
        )
    )
    employee.user_id = user.id
    employee.status = EmployeeStatus.ACTIVE.value
    invite.accepted_at = now
    await db.commit()

    email_adapter.send(
        EmailMessage(
            to=body.email,
            subject="Verify your Dayflow account",
            body="Your Dayflow account is ready. Check this message as the activation verification payload.",
        )
    )
    return ActivateAccountResponse(
        status="verification_sent",
        detail="Check your work email to verify this account.",
    )


@router.get("/me", response_model=SessionUser)
async def me(
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> SessionUser:
    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == principal.user_id,
            OrganizationMembership.organization_id == principal.organization_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No organization membership.")
    return await _session_user(db, principal.user, membership)
