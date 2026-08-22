from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class SalaryComponentConfigIn(BaseModel):
    code: str
    calculation_type: str | None = None
    rate: Decimal | None = Field(default=None, max_digits=8, decimal_places=4)
    amount: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)


class EmployeeSalaryPatchRequest(BaseModel):
    monthly_wage: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    effective_from: date | None = None
    components: list[SalaryComponentConfigIn] | None = None


class SalaryLineOut(BaseModel):
    code: str
    name: str
    kind: str
    calculation_type: str
    rate: Decimal | None
    amount: Decimal
    editable: bool

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.01'))}"

    @field_serializer("rate")
    def serialize_rate(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return f"{value.quantize(Decimal('0.01'))}"


class EmployeeSalaryOut(BaseModel):
    employee_id: UUID
    monthly_wage: Decimal
    currency: str
    effective_from: date
    gross_amount: Decimal
    deduction_amount: Decimal
    net_amount: Decimal
    employer_amount: Decimal
    lines: list[SalaryLineOut]

    @field_serializer("monthly_wage", "gross_amount", "deduction_amount", "net_amount", "employer_amount")
    def serialize_money(self, value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.01'))}"


class EmployeeSalaryInputsOut(BaseModel):
    employee_id: UUID
    employee_name: str
    monthly_wage: Decimal
    net_amount: Decimal
    components: list[SalaryLineOut]

    @field_serializer("monthly_wage", "net_amount")
    def serialize_wage(self, value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.01'))}"


class PayrollRecordLineOut(BaseModel):
    code: str
    label: str
    amount: Decimal
    kind: str | None = None

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.01'))}"


class PayrollRecordDetailOut(BaseModel):
    id: UUID
    employee_id: UUID
    gross_amount: Decimal
    deduction_amount: Decimal
    net_amount: Decimal
    currency: str
    published_at: datetime | None = None
    lines: list[PayrollRecordLineOut] = []

    @field_serializer("gross_amount", "deduction_amount", "net_amount")
    def serialize_money(self, value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.01'))}"


class PayrollPeriodActionOut(BaseModel):
    id: UUID
    starts_on: date
    ends_on: date
    pay_date: date
    status: str
    records: list[PayrollRecordDetailOut]
