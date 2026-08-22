import hashlib
from datetime import datetime

from app.domain.roles import Role


class IdentityError(ValueError):
    pass


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_signup_role() -> None:
    """Public registration never assigns a role. Roles arrive on an invite."""
    return None


def role_from_invite(invite_role: str) -> Role:
    """Activation never reads a role from the public request body."""
    return Role(invite_role)


def assert_invite_usable(*, accepted_at: datetime | None, expires_at: datetime, now: datetime) -> None:
    if accepted_at is not None:
        raise IdentityError("This invite has already been used.")
    if expires_at <= now:
        raise IdentityError("This invite has expired.")


def is_hr(role: Role) -> bool:
    return role is Role.HR


def can_read_employee(*, role: Role, actor_employee_id, target_employee_id) -> bool:
    if role is Role.HR:
        return True
    return actor_employee_id == target_employee_id


def can_edit_job_or_salary(role: Role) -> bool:
    return role is Role.HR
