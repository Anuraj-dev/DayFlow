from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.identity import Organization


class Employee(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("organization_id", "employee_code"),
        UniqueConstraint("user_id", name="uq_employees_user_id"),
        UniqueConstraint("id", "organization_id", name="uq_employees_id_org"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(Text)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    nationality: Mapped[str | None] = mapped_column(String(64))
    gender: Mapped[str | None] = mapped_column(String(32))
    marital_status: Mapped[str | None] = mapped_column(String(32))
    personal_email: Mapped[str | None] = mapped_column(String(255))
    bank_account_number: Mapped[str | None] = mapped_column(String(64))
    bank_name: Mapped[str | None] = mapped_column(String(120))
    ifsc: Mapped[str | None] = mapped_column(String(32))
    pan: Mapped[str | None] = mapped_column(String(16))
    uan: Mapped[str | None] = mapped_column(String(32))
    profile_image_key: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    joined_on: Mapped[date | None] = mapped_column(Date)
    manager_employee_id: Mapped[UUID | None] = mapped_column(ForeignKey("employees.id"))

    organization: Mapped["Organization"] = relationship(back_populates="employees")
    job_assignments: Mapped[list["JobAssignment"]] = relationship(back_populates="employee")
    documents: Mapped[list["EmployeeDocument"]] = relationship(back_populates="employee")


class JobAssignment(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "job_assignments"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    department: Mapped[str] = mapped_column(String(120), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(32), nullable=False, default="FULL_TIME")
    location: Mapped[str] = mapped_column(String(120), nullable=False, default="Office")
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date)

    employee: Mapped[Employee] = relationship(back_populates="job_assignments")


class EmployeeDocument(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "employee_documents"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="HR_AND_SELF")
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    employee: Mapped[Employee] = relationship(back_populates="documents")
