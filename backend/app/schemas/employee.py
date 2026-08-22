from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domain.roles import EmployeeStatus, Role


class EmployeeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_code: str
    first_name: str
    last_name: str
    status: EmployeeStatus
    phone: str | None = None
    address: str | None = None
    email: EmailStr | None = None
    role: Role | None = None
    department: str | None = None
    title: str | None = None
    employment_type: str | None = None
    location: str | None = None
    joined_on: date | None = None
    presence: str | None = None


class EmployeeDetail(EmployeeSummary):
    date_of_birth: date | None = None
    nationality: str | None = None
    gender: str | None = None
    marital_status: str | None = None
    personal_email: EmailStr | None = None
    bank_account_number: str | None = None
    bank_name: str | None = None
    ifsc: str | None = None
    pan: str | None = None
    uan: str | None = None


class EmployeeUpdateRequest(BaseModel):
    phone: str | None = None
    address: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    status: EmployeeStatus | None = None
    title: str | None = None
    department: str | None = None
    employment_type: str | None = None
    location: str | None = None
    date_of_birth: date | None = None
    nationality: str | None = Field(default=None, max_length=64)
    gender: str | None = Field(default=None, max_length=32)
    marital_status: str | None = Field(default=None, max_length=32)
    personal_email: EmailStr | None = None
    bank_account_number: str | None = Field(default=None, max_length=64)
    bank_name: str | None = Field(default=None, max_length=120)
    ifsc: str | None = Field(default=None, max_length=32)
    pan: str | None = Field(default=None, max_length=16)
    uan: str | None = Field(default=None, max_length=32)

    @field_validator(
        "phone",
        "address",
        "nationality",
        "gender",
        "marital_status",
        "personal_email",
        "bank_account_number",
        "bank_name",
        "ifsc",
        "pan",
        "uan",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        if value == "":
            return None
        return value


class EmployeeCreateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    title: str | None = None
    department: str | None = None
    location: str | None = None
    joined_on: date | None = None


class EmployeeHireResponse(BaseModel):
    employee: EmployeeSummary
    invite_token: str
    employee_code: str
    detail: str
