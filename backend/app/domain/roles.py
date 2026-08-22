from enum import StrEnum


class Role(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    HR = "HR"


class UserStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class EmployeeStatus(StrEnum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
