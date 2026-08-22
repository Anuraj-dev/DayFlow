import hashlib
from datetime import datetime

from app.domain.roles import EmployeeStatus, Role


class IdentityError(ValueError):
    pass


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(value: str) -> str:
    return str(value).strip().casefold()


def _name_letters(value: str) -> str:
    letters = "".join(ch for ch in value.upper() if "A" <= ch <= "Z")
    padded = letters + "X"
    return padded[:2]


def build_employee_code(
    *,
    prefix: str = "OI",
    first_name: str,
    last_name: str,
    year: int,
    serial: int,
) -> str:
    return f"{prefix}{_name_letters(first_name)}{_name_letters(last_name)}{year}{serial:04d}"


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


def assert_employee_can_activate(*, user_id, status: str) -> None:
    if user_id is not None or status != EmployeeStatus.INVITED.value:
        raise IdentityError("This account has already been activated.")


def is_hr(role: Role) -> bool:
    return role is Role.HR


def can_read_employee(*, role: Role, actor_employee_id, target_employee_id) -> bool:
    """Directory cards are org-wide and view-only. Salary and edits stay HR-gated."""
    del actor_employee_id, target_employee_id
    return role in {Role.HR, Role.EMPLOYEE}


def can_read_private_employee_fields(*, role: Role, actor_employee_id, target_employee_id) -> bool:
    """Private and bank fields are self or same-org HR only. Directory/coworker GET omit them."""
    if role is Role.HR:
        return True
    return actor_employee_id is not None and actor_employee_id == target_employee_id


def can_edit_job_or_salary(role: Role) -> bool:
    return role is Role.HR


EMPLOYEE_SELF_EDIT_FIELDS = frozenset({"phone", "address"})
PRIVATE_EMPLOYEE_FIELDS = frozenset(
    {
        "date_of_birth",
        "nationality",
        "gender",
        "marital_status",
        "personal_email",
        "bank_account_number",
        "bank_name",
        "ifsc",
        "pan",
        "uan",
    }
)
HR_EMPLOYEE_EDIT_FIELDS = frozenset(
    {
        "phone",
        "address",
        "first_name",
        "last_name",
        "status",
        "title",
        "department",
        "employment_type",
        "location",
        *PRIVATE_EMPLOYEE_FIELDS,
    }
)


def can_edit_employee(*, role: Role, actor_employee_id, target_employee_id) -> bool:
    if role is Role.HR:
        return True
    return actor_employee_id == target_employee_id


def allowed_employee_patch_fields(role: Role) -> frozenset[str]:
    if role is Role.HR:
        return HR_EMPLOYEE_EDIT_FIELDS
    return EMPLOYEE_SELF_EDIT_FIELDS


def assert_employee_patch_allowed(*, role: Role, fields: set[str]) -> None:
    allowed = allowed_employee_patch_fields(role)
    forbidden = fields - allowed
    if forbidden:
        raise IdentityError(f"Cannot edit fields: {', '.join(sorted(forbidden))}.")
