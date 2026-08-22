from decimal import Decimal
from enum import StrEnum


class PayrollPeriodStatus(StrEnum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"
    PUBLISHED = "PUBLISHED"


class ComponentKind(StrEnum):
    EARNING = "EARNING"
    DEDUCTION = "DEDUCTION"


class PayrollError(ValueError):
    pass


def net_amount(gross: Decimal, deductions: Decimal) -> Decimal:
    return gross - deductions


def signed_line_amount(kind: ComponentKind | str, amount: Decimal) -> Decimal:
    if ComponentKind(kind) is ComponentKind.DEDUCTION:
        return -abs(amount)
    return amount


def totals_from_components(items: list[tuple[ComponentKind | str, Decimal]]) -> tuple[Decimal, Decimal, Decimal]:
    gross = Decimal("0.00")
    deductions = Decimal("0.00")
    for kind, amount in items:
        if ComponentKind(kind) is ComponentKind.DEDUCTION:
            deductions += abs(amount)
        else:
            gross += amount
    return gross, deductions, net_amount(gross, deductions)


def assert_can_finalize(*, status: PayrollPeriodStatus, net: Decimal) -> None:
    if status is not PayrollPeriodStatus.DRAFT:
        raise PayrollError("Only a draft payroll period can be finalized.")
    if net < 0:
        raise PayrollError("Net pay cannot be negative.")


def assert_can_publish(status: PayrollPeriodStatus) -> None:
    if status is not PayrollPeriodStatus.FINALIZED:
        raise PayrollError("A payroll period must be finalized before it is published.")


def assert_mutable(status: PayrollPeriodStatus) -> None:
    if status is not PayrollPeriodStatus.DRAFT:
        raise PayrollError("Finalized payroll records are immutable.")
