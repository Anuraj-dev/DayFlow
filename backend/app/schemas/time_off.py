from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LeaveBalanceOut(BaseModel):
    leave_type: str
    remaining_days: float
    granted_days: float
    used_days: float


class LeaveRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    leave_type: str
    starts_on: date
    ends_on: date
    counted_days: float
    reason: str
    status: str
    employee_name: str | None = None
    review_comment: str | None = None
    submitted_at: datetime | None = None
    has_certificate: bool = False
    certificate_download_url: str | None = None
    certificate_expires_at: datetime | None = None


class TimeOffHome(BaseModel):
    role: str
    employee_id: UUID | None
    balances: list[LeaveBalanceOut]
    requests: list[LeaveRequestOut]
    pending_queue: list[LeaveRequestOut]


class LeaveRequestCreate(BaseModel):
    leave_type: str
    starts_on: date
    ends_on: date
    reason: str


class LeaveDecisionRequest(BaseModel):
    comment: str | None = None
