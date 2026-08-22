from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.domain.roles import EmployeeStatus, Role


class EmployeeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_code: str
    first_name: str
    last_name: str
    status: EmployeeStatus
    email: EmailStr | None = None
    role: Role | None = None
    department: str | None = None
    title: str | None = None
    joined_on: date | None = None
