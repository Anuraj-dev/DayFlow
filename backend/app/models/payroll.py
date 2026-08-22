from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey


class SalaryComponent(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "salary_components"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    calculation_type: Mapped[str] = mapped_column(String(32), nullable=False, default="FIXED")
    taxable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EmployeeSalaryComponent(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "employee_salary_components"

    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    salary_component_id: Mapped[UUID] = mapped_column(ForeignKey("salary_components.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)


class PayrollPeriod(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "payroll_periods"

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    finalized_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    records: Mapped[list["PayrollRecord"]] = relationship(back_populates="period")


class PayrollRecord(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "payroll_records"

    payroll_period_id: Mapped[UUID] = mapped_column(ForeignKey("payroll_periods.id"), nullable=False)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deduction_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    payslip_storage_key: Mapped[str | None] = mapped_column(String(512))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    period: Mapped[PayrollPeriod] = relationship(back_populates="records")
    lines: Mapped[list["PayrollRecordLine"]] = relationship(back_populates="record")


class PayrollRecordLine(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "payroll_record_lines"

    payroll_record_id: Mapped[UUID] = mapped_column(ForeignKey("payroll_records.id"), nullable=False)
    salary_component_id: Mapped[UUID | None] = mapped_column(ForeignKey("salary_components.id"))
    label_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    record: Mapped[PayrollRecord] = relationship(back_populates="lines")
