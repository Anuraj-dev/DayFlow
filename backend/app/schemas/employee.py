from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
