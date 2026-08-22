from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AttendanceSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    work_date: date
    check_in_at: datetime
    check_out_at: datetime | None
    source: str
    status: str
    worked_minutes: int | None


class OpenSessionOut(BaseModel):
    id: UUID
    check_in_at: datetime


class AttendanceExceptionOut(BaseModel):
    id: UUID
    employee_id: UUID
    employee_name: str | None = None
    kind: str
    status: str
    work_date: date | None = None
    current_check_in_at: datetime | None = None
    current_check_out_at: datetime | None = None
    proposed_check_in_at: datetime | None = None
    proposed_check_out_at: datetime | None = None
    reason: str | None = None


class AttendanceHome(BaseModel):
    role: str
    employee_id: UUID | None
    sessions: list[AttendanceSessionOut]
    open_session: OpenSessionOut | None
    exceptions: list[AttendanceExceptionOut]


class CorrectionCreateRequest(BaseModel):
    attendance_session_id: UUID
    proposed_check_in_at: datetime
    proposed_check_out_at: datetime | None = None
    reason: str


class CorrectionReviewRequest(BaseModel):
    decision: str
    comment: str | None = None


class CorrectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attendance_session_id: UUID
    requested_by: UUID
    proposed_check_in_at: datetime
    proposed_check_out_at: datetime | None
    reason: str
    status: str
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_comment: str | None
