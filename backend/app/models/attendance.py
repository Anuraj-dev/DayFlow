from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Time, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class WorkPolicy(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "work_policies"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    workweek: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=lambda: [0, 1, 2, 3, 4])
    full_day_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=480)
    half_day_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=240)
    late_after_local_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(10, 0))


class Holiday(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "holidays"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str | None] = mapped_column(String(120))


class AttendanceSession(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "attendance_sessions"
    __table_args__ = (
        Index(
            "uq_attendance_open_session",
            "employee_id",
            unique=True,
            postgresql_where=text("status = 'OPEN' AND check_out_at IS NULL"),
        ),
    )

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="SERVER")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    worked_minutes: Mapped[int | None] = mapped_column(Integer)

    corrections: Mapped[list["AttendanceCorrectionRequest"]] = relationship(back_populates="session")


class AttendanceCorrectionRequest(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "attendance_correction_requests"

    attendance_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("attendance_sessions.id"), nullable=False
    )
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    proposed_check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    proposed_check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_comment: Mapped[str | None] = mapped_column(String(500))

    session: Mapped[AttendanceSession] = relationship(back_populates="corrections")
