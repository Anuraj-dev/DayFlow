from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.employee import Employee


class Organization(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")

    memberships: Mapped[list["OrganizationMembership"]] = relationship(back_populates="organization")
    employees: Mapped[list["Employee"]] = relationship(back_populates="organization")


class User(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (Index("uq_users_email_lower", text("lower(email)"), unique=True),)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["OrganizationMembership"]] = relationship(back_populates="user")


class OrganizationMembership(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id"),
        UniqueConstraint("user_id", name="uq_memberships_user_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class AccountInvite(UUIDPrimaryKey, TimestampMixin, Base):
    __tablename__ = "account_invites"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        ForeignKeyConstraint(
            ["employee_id", "organization_id"],
            ["employees.id", "employees.organization_id"],
            name="fk_account_invites_employee_org",
        ),
        Index(
            "uq_account_invites_open_employee",
            "employee_id",
            unique=True,
            postgresql_where=text("accepted_at IS NULL"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
