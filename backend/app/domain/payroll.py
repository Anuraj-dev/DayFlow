from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum


class PayrollPeriodStatus(StrEnum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"
    PUBLISHED = "PUBLISHED"


class ComponentKind(StrEnum):
    EARNING = "EARNING"
    DEDUCTION = "DEDUCTION"
    EMPLOYER = "EMPLOYER"


class CalculationType(StrEnum):
    FIXED = "FIXED"
    PERCENT_OF_WAGE = "PERCENT_OF_WAGE"
    PERCENT_OF_BASIC = "PERCENT_OF_BASIC"
    REMAINDER = "REMAINDER"


class PayrollError(ValueError):
    pass


MONEY = Decimal("0.01")
HUNDRED = Decimal("100")
DEFAULT_MONTHLY_WAGE = Decimal("50000.00")
BASIC_CODE = "BASIC"
HRA_CODE = "HRA"
REMAINDER_CODE = "FIXED_ALLOW"
PF_CODE = "PF"
PF_EMPLOYER_CODE = "PF_EMPLOYER"
PT_CODE = "PT"

LINE_ORDER = (
    "BASIC",
    "HRA",
    "STD_ALLOW",
    "PERF_BONUS",
    "LTA",
    "FIXED_ALLOW",
    "PF",
    "PT",
    "PF_EMPLOYER",
)


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SalaryStructureLine:
    code: str
    name: str
    kind: ComponentKind | str
    calculation_type: CalculationType | str
    rate: Decimal | None = None
    amount: Decimal | None = None


@dataclass(frozen=True)
class ComputedSalaryLine:
    code: str
    name: str
    kind: ComponentKind
    calculation_type: CalculationType
    rate: Decimal | None
    amount: Decimal
    editable: bool


@dataclass(frozen=True)
class ComputedSalary:
    monthly_wage: Decimal
    lines: tuple[ComputedSalaryLine, ...]
    gross_amount: Decimal
    deduction_amount: Decimal
    net_amount: Decimal
    employer_amount: Decimal


def default_salary_structure() -> list[SalaryStructureLine]:
    return [
        SalaryStructureLine(
            code="BASIC",
            name="Basic",
            kind=ComponentKind.EARNING,
            calculation_type=CalculationType.PERCENT_OF_WAGE,
            rate=Decimal("50.00"),
        ),
        SalaryStructureLine(
            code="HRA",
            name="House rent allowance",
            kind=ComponentKind.EARNING,
            calculation_type=CalculationType.PERCENT_OF_BASIC,
            rate=Decimal("50.00"),
        ),
        SalaryStructureLine(
            code="STD_ALLOW",
            name="Standard Allowance",
            kind=ComponentKind.EARNING,
            calculation_type=CalculationType.FIXED,
            amount=Decimal("4167.00"),
        ),
        SalaryStructureLine(
            code="PERF_BONUS",
            name="Performance Bonus",
            kind=ComponentKind.EARNING,
            calculation_type=CalculationType.PERCENT_OF_WAGE,
            rate=Decimal("8.33"),
        ),
        SalaryStructureLine(
            code="LTA",
            name="Leave travel allowance",
            kind=ComponentKind.EARNING,
            calculation_type=CalculationType.PERCENT_OF_WAGE,
            rate=Decimal("8.33"),
        ),
        SalaryStructureLine(
            code=REMAINDER_CODE,
            name="Fixed Allowance",
            kind=ComponentKind.EARNING,
            calculation_type=CalculationType.REMAINDER,
        ),
        SalaryStructureLine(
            code=PF_CODE,
            name="Employee provident fund",
            kind=ComponentKind.DEDUCTION,
            calculation_type=CalculationType.PERCENT_OF_BASIC,
            rate=Decimal("12.00"),
        ),
        SalaryStructureLine(
            code=PF_EMPLOYER_CODE,
            name="Employer provident fund",
            kind=ComponentKind.EMPLOYER,
            calculation_type=CalculationType.PERCENT_OF_BASIC,
            rate=Decimal("12.00"),
        ),
        SalaryStructureLine(
            code=PT_CODE,
            name="Professional tax",
            kind=ComponentKind.DEDUCTION,
            calculation_type=CalculationType.FIXED,
            amount=Decimal("200.00"),
        ),
    ]


def net_amount(gross: Decimal, deductions: Decimal) -> Decimal:
    return gross - deductions


def signed_line_amount(kind: ComponentKind | str, amount: Decimal) -> Decimal:
    if ComponentKind(kind) is ComponentKind.DEDUCTION:
        return -abs(amount)
    return amount


def line_is_editable(kind: ComponentKind | str, calculation_type: CalculationType | str) -> bool:
    return (
        ComponentKind(kind) is ComponentKind.EARNING
        and CalculationType(calculation_type) is not CalculationType.REMAINDER
    )


def assignment_covers(*, effective_from: date, effective_to: date | None, as_of: date) -> bool:
    if effective_from > as_of:
        return False
    if effective_to is not None and effective_to < as_of:
        return False
    return True


def totals_from_components(items: list[tuple[ComponentKind | str, Decimal]]) -> tuple[Decimal, Decimal, Decimal]:
    gross = Decimal("0.00")
    deductions = Decimal("0.00")
    for kind, amount in items:
        component_kind = ComponentKind(kind)
        if component_kind is ComponentKind.DEDUCTION:
            deductions += abs(amount)
        elif component_kind is ComponentKind.EARNING:
            gross += amount
    return gross, deductions, net_amount(gross, deductions)


def assert_can_finalize(*, status: PayrollPeriodStatus, net: Decimal) -> None:
    if status is not PayrollPeriodStatus.DRAFT:
        raise PayrollError("Only a draft payroll period can be finalized.")
    if net < 0:
        raise PayrollError("Net pay cannot be negative.")


def assert_no_attendance_blockers(*, open_session_count: int, pending_correction_count: int) -> None:
    if open_session_count:
        raise PayrollError("Open attendance sessions in this period block finalization.")
    if pending_correction_count:
        raise PayrollError("Pending attendance corrections in this period block finalization.")


def prorate_computed_salary(
    computed: ComputedSalary,
    *,
    payable_days: Decimal,
    scheduled_days: Decimal,
) -> ComputedSalary:
    scheduled = Decimal(scheduled_days)
    payable = Decimal(payable_days)
    if scheduled <= 0:
        raise PayrollError("A payroll period needs scheduled working days before it can be finalized.")
    if payable < 0:
        raise PayrollError("Payable days cannot be negative.")
    factor = payable / scheduled
    amounts: dict[str, Decimal] = {}
    for line in computed.lines:
        if line.kind is ComponentKind.EARNING:
            amounts[line.code] = money(line.amount * factor)
        elif line.code == PT_CODE:
            amounts[line.code] = line.amount
        else:
            amounts[line.code] = line.amount

    basic_amount = amounts.get(BASIC_CODE, Decimal("0.00"))
    for line in computed.lines:
        if line.kind is ComponentKind.EARNING or line.code == PT_CODE:
            continue
        if line.calculation_type is CalculationType.PERCENT_OF_BASIC:
            assert line.rate is not None
            amounts[line.code] = _percent(basic_amount, line.rate)
        else:
            amounts[line.code] = money(line.amount * factor)

    prorated_lines = tuple(
        ComputedSalaryLine(
            code=line.code,
            name=line.name,
            kind=line.kind,
            calculation_type=line.calculation_type,
            rate=line.rate,
            amount=amounts[line.code],
            editable=line.editable,
        )
        for line in computed.lines
    )
    items = [(line.kind, line.amount) for line in prorated_lines]
    gross, deductions, net = totals_from_components(items)
    employer = sum(
        (line.amount for line in prorated_lines if line.kind is ComponentKind.EMPLOYER),
        Decimal("0.00"),
    )
    return ComputedSalary(
        monthly_wage=computed.monthly_wage,
        lines=prorated_lines,
        gross_amount=gross,
        deduction_amount=deductions,
        net_amount=net,
        employer_amount=employer,
    )


def assert_can_publish(status: PayrollPeriodStatus) -> None:
    if status is not PayrollPeriodStatus.FINALIZED:
        raise PayrollError("A payroll period must be finalized before it is published.")


def assert_mutable(status: PayrollPeriodStatus) -> None:
    if status is not PayrollPeriodStatus.DRAFT:
        raise PayrollError("Finalized payroll records are immutable.")


def _require_non_negative(value: Decimal, label: str) -> Decimal:
    if value < 0:
        raise PayrollError(f"{label} cannot be negative.")
    return value


def _percent(base: Decimal, rate: Decimal) -> Decimal:
    return money(base * rate / HUNDRED)


def _normalized_lines(structure: Sequence[SalaryStructureLine]) -> list[SalaryStructureLine]:
    seen: set[str] = set()
    normalized: list[SalaryStructureLine] = []
    for raw in structure:
        code = raw.code.strip().upper()
        if not code:
            raise PayrollError("Salary component code is required.")
        if code in seen:
            raise PayrollError(f"Duplicate salary component {code}.")
        seen.add(code)
        kind = ComponentKind(raw.kind)
        calculation_type = CalculationType(raw.calculation_type)
        rate = money(raw.rate) if raw.rate is not None else None
        amount = money(raw.amount) if raw.amount is not None else None
        if rate is not None:
            _require_non_negative(rate, f"{code} rate")
        if amount is not None:
            _require_non_negative(amount, f"{code} amount")
        if calculation_type is CalculationType.PERCENT_OF_BASIC:
            if code == BASIC_CODE:
                raise PayrollError("Basic cannot be a percentage of Basic: that is a cycle.")
            if kind is ComponentKind.EARNING and code != HRA_CODE:
                raise PayrollError("Only HRA may be a percentage of Basic among earnings.")
        if calculation_type is CalculationType.REMAINDER and kind is not ComponentKind.EARNING:
            raise PayrollError("Remainder is only valid for an earning.")
        if calculation_type in {CalculationType.PERCENT_OF_WAGE, CalculationType.PERCENT_OF_BASIC} and rate is None:
            raise PayrollError(f"{code} requires a rate.")
        if calculation_type is CalculationType.FIXED and amount is None:
            raise PayrollError(f"{code} requires a fixed amount.")
        normalized.append(
            SalaryStructureLine(
                code=code,
                name=raw.name,
                kind=kind,
                calculation_type=calculation_type,
                rate=rate,
                amount=amount,
            )
        )
    remainder_codes = [
        line.code for line in normalized if CalculationType(line.calculation_type) is CalculationType.REMAINDER
    ]
    if len(remainder_codes) > 1:
        raise PayrollError("Only one remainder earning is allowed.")
    return normalized


def compute_salary(monthly_wage: Decimal, structure: Sequence[SalaryStructureLine]) -> ComputedSalary:
    wage = money(_require_non_negative(monthly_wage, "Monthly wage"))
    lines = _normalized_lines(structure)
    by_code = {line.code: line for line in lines}

    basic_line = by_code.get(BASIC_CODE)
    needs_basic = any(CalculationType(line.calculation_type) is CalculationType.PERCENT_OF_BASIC for line in lines)
    if needs_basic and basic_line is None:
        raise PayrollError("A Basic component is required before a percentage of Basic can be computed.")
    if basic_line is not None and CalculationType(basic_line.calculation_type) in {
        CalculationType.PERCENT_OF_BASIC,
        CalculationType.REMAINDER,
    }:
        raise PayrollError("Basic cannot depend on itself: that is a cycle.")

    amounts: dict[str, Decimal] = {}

    def compute_line(line: SalaryStructureLine) -> Decimal:
        calculation_type = CalculationType(line.calculation_type)
        if calculation_type is CalculationType.FIXED:
            assert line.amount is not None
            return line.amount
        if calculation_type is CalculationType.PERCENT_OF_WAGE:
            assert line.rate is not None
            return _percent(wage, line.rate)
        raise PayrollError(f"{line.code} cannot be computed yet.")

    if basic_line is not None and CalculationType(basic_line.calculation_type) is not CalculationType.REMAINDER:
        amounts[BASIC_CODE] = compute_line(basic_line)

    basic_amount = amounts.get(BASIC_CODE, Decimal("0.00"))

    for line in lines:
        calculation_type = CalculationType(line.calculation_type)
        if line.code in amounts or calculation_type is CalculationType.REMAINDER:
            continue
        if calculation_type is CalculationType.PERCENT_OF_BASIC:
            if BASIC_CODE not in amounts:
                raise PayrollError("A Basic component is required before a percentage of Basic can be computed.")
            assert line.rate is not None
            amounts[line.code] = _percent(basic_amount, line.rate)
        else:
            amounts[line.code] = compute_line(line)

    remainder_lines = [line for line in lines if CalculationType(line.calculation_type) is CalculationType.REMAINDER]
    if remainder_lines:
        allocated = sum(
            (
                amounts[line.code]
                for line in lines
                if ComponentKind(line.kind) is ComponentKind.EARNING
                and CalculationType(line.calculation_type) is not CalculationType.REMAINDER
            ),
            Decimal("0.00"),
        )
        remaining = money(wage - allocated)
        if remaining < 0:
            raise PayrollError("Salary components exceed monthly wage.")
        for line in remainder_lines:
            amounts[line.code] = remaining

    computed: list[ComputedSalaryLine] = []
    order_index = {code: index for index, code in enumerate(LINE_ORDER)}
    for line in sorted(lines, key=lambda item: (order_index.get(item.code, len(LINE_ORDER)), item.code)):
        kind = ComponentKind(line.kind)
        calculation_type = CalculationType(line.calculation_type)
        computed.append(
            ComputedSalaryLine(
                code=line.code,
                name=line.name,
                kind=kind,
                calculation_type=calculation_type,
                rate=line.rate,
                amount=amounts[line.code],
                editable=line_is_editable(kind, calculation_type),
            )
        )

    items = [(line.kind, line.amount) for line in computed]
    gross, deductions, net = totals_from_components(items)
    employer = sum(
        (line.amount for line in computed if line.kind is ComponentKind.EMPLOYER),
        Decimal("0.00"),
    )
    return ComputedSalary(
        monthly_wage=wage,
        lines=tuple(computed),
        gross_amount=gross,
        deduction_amount=deductions,
        net_amount=net,
        employer_amount=employer,
    )
