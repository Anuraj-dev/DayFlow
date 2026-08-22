from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class LeaveType(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "leave_types"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_balance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LeaveBalance(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "leave_balances"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    leave_type_id: Mapped[UUID] = mapped_column(ForeignKey("leave_types.id"), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    granted_days: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    used_days: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    adjustment_days: Mapped[float] = mapped_column(Float, nullable=False, default=0)


class LeaveRequest(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "leave_requests"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    leave_type_id: Mapped[UUID] = mapped_column(ForeignKey("leave_types.id"), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    counted_days: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_comment: Mapped[str | None] = mapped_column(Text)
    certificate_storage_key: Mapped[str | None] = mapped_column(String(512))
    certificate_content_type: Mapped[str | None] = mapped_column(String(128))

    events: Mapped[list["LeaveRequestEvent"]] = relationship(back_populates="leave_request")


class LeaveRequestEvent(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "leave_request_events"

    leave_request_id: Mapped[UUID] = mapped_column(ForeignKey("leave_requests.id"), nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    leave_request: Mapped[LeaveRequest] = relationship(back_populates="events")
