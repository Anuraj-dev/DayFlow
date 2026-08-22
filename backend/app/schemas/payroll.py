from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class SalaryComponentAmountIn(BaseModel):
    code: str
    amount: Decimal = Field(..., max_digits=12, decimal_places=2)


class SalaryComponentPatchRequest(BaseModel):
    employee_id: UUID
    period_id: UUID
    components: list[SalaryComponentAmountIn]


class SalaryComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    kind: str
    amount: Decimal

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.01'))}"


class SalaryComponentPatchResponse(BaseModel):
    employee_id: UUID
    components: list[SalaryComponentOut]


class PayrollRecordLineOut(BaseModel):
    code: str
    label: str
    amount: Decimal

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
