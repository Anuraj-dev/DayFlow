from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.email import EmailMessage, email_adapter
from app.api.deps import CurrentPrincipal, get_current_principal
from app.core.db import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.identity import (
    IdentityError,
    assert_employee_can_activate,
    assert_invite_usable,
    hash_invite_token,
    role_from_invite,
)
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
_MISSING_USER_HASH = hash_password("dayflow-missing-user")


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
    if user is None:
        verify_password(body.password, _MISSING_USER_HASH)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials.")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials.")
    if user.status != UserStatus.ACTIVE.value:
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
    invite = await db.scalar(
        select(AccountInvite)
        .where(AccountInvite.token_hash == hash_invite_token(body.token))
        .with_for_update()
    )
    if invite is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite is invalid.")

    now = datetime.now(UTC)
    try:
        assert_invite_usable(accepted_at=invite.accepted_at, expires_at=invite.expires_at, now=now)
    except IdentityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    employee = await db.scalar(
        select(Employee).where(Employee.id == invite.employee_id).with_for_update()
    )
    if employee is None or employee.employee_code != body.employee_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite is invalid.")
    if invite.email.casefold() != str(body.email).casefold():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite is invalid.")

    try:
        assert_employee_can_activate(user_id=employee.user_id, status=employee.status)
    except IdentityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    existing_user = await db.scalar(select(User).where(User.email == body.email))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This email is already in use.")

    role = role_from_invite(invite.role)
    user = User(
        email=str(body.email),
        password_hash=hash_password(body.password),
        email_verified_at=now,
        status=UserStatus.ACTIVE.value,
    )
    db.add(user)
    try:
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
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email or invite cannot be used.",
        ) from exc

    email_adapter.send(
        EmailMessage(
            to=str(body.email),
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
