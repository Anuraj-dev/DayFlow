from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.domain.roles import Role


class SignInRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=12)


class ActivateAccountRequest(BaseModel):
    employee_code: str
    email: EmailStr
    token: str
    password: str = Field(min_length=12)


class ActivateAccountResponse(BaseModel):
    status: str
    detail: str


class SessionUser(BaseModel):
    id: UUID
    email: EmailStr
    role: Role
    organization_id: UUID
    employee_id: UUID | None
    first_name: str | None
    last_name: str | None
    employee_code: str | None


class SignInResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: SessionUser


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=12)


class ChangePasswordResponse(BaseModel):
    detail: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    detail: str
