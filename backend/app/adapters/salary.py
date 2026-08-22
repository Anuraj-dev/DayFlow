from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.payroll import (
    DEFAULT_MONTHLY_WAGE,
    CalculationType,
    ComponentKind,
    ComputedSalary,
    PayrollError,
    SalaryStructureLine,
    assignment_covers,
    compute_salary,
    default_salary_structure,
    line_is_editable,
    money,
)
from app.models import Employee, EmployeeSalaryComponent, EmployeeWage, SalaryComponent


def _pick_covering[T](rows: list[T], as_of: date, *, start, end) -> T | None:
    covering = [
        row
        for row in rows
        if assignment_covers(effective_from=start(row), effective_to=end(row), as_of=as_of)
    ]
    if not covering:
        return None
    return max(covering, key=start)


def structure_from_assignments(
    pairs: list[tuple[EmployeeSalaryComponent, SalaryComponent]],
) -> list[SalaryStructureLine]:
    lines: list[SalaryStructureLine] = []
    for assignment, component in pairs:
        calculation_type = CalculationType(assignment.calculation_type)
        lines.append(
            SalaryStructureLine(
                code=component.code,
                name=component.name,
                kind=component.kind,
                calculation_type=calculation_type,
                rate=assignment.rate,
                amount=assignment.amount if calculation_type is CalculationType.FIXED else None,
            )
        )
    return lines


async def ensure_org_components(db: AsyncSession, organization_id: UUID) -> dict[str, SalaryComponent]:
    existing = list(
        await db.scalars(select(SalaryComponent).where(SalaryComponent.organization_id == organization_id))
    )
    by_code = {component.code.upper(): component for component in existing}
    created = False
    for line in default_salary_structure():
        if line.code in by_code:
            component = by_code[line.code]
            component.calculation_type = CalculationType(line.calculation_type).value
            component.kind = ComponentKind(line.kind).value
            component.name = line.name
            component.active = True
            continue
        component = SalaryComponent(
            organization_id=organization_id,
            name=line.name,
            code=line.code,
            kind=ComponentKind(line.kind).value,
            calculation_type=CalculationType(line.calculation_type).value,
            taxable=ComponentKind(line.kind) is ComponentKind.EARNING,
            active=True,
        )
        db.add(component)
        by_code[line.code] = component
        created = True
    if created:
        await db.flush()
    return by_code


async def load_wage_rows(db: AsyncSession, employee_id: UUID) -> list[EmployeeWage]:
    return list(await db.scalars(select(EmployeeWage).where(EmployeeWage.employee_id == employee_id)))


async def load_assignment_rows(
    db: AsyncSession, organization_id: UUID, employee_id: UUID
) -> list[tuple[EmployeeSalaryComponent, SalaryComponent]]:
    return list(
        (
            await db.execute(
                select(EmployeeSalaryComponent, SalaryComponent)
                .join(SalaryComponent, SalaryComponent.id == EmployeeSalaryComponent.salary_component_id)
                .where(
                    EmployeeSalaryComponent.employee_id == employee_id,
                    SalaryComponent.organization_id == organization_id,
                )
            )
        ).all()
    )


def effective_wage(rows: list[EmployeeWage], as_of: date) -> EmployeeWage | None:
    return _pick_covering(rows, as_of, start=lambda row: row.effective_from, end=lambda row: row.effective_to)


def effective_assignments(
    pairs: list[tuple[EmployeeSalaryComponent, SalaryComponent]], as_of: date
) -> list[tuple[EmployeeSalaryComponent, SalaryComponent]]:
    grouped: dict[UUID, list[tuple[EmployeeSalaryComponent, SalaryComponent]]] = {}
    for assignment, component in pairs:
        grouped.setdefault(component.id, []).append((assignment, component))
    selected: list[tuple[EmployeeSalaryComponent, SalaryComponent]] = []
    for group in grouped.values():
        picked = _pick_covering(
            group,
            as_of,
            start=lambda row: row[0].effective_from,
            end=lambda row: row[0].effective_to,
        )
        if picked is not None:
            selected.append(picked)
    return selected


async def load_computed_salary(
    db: AsyncSession, organization_id: UUID, employee_id: UUID, as_of: date
) -> tuple[EmployeeWage, ComputedSalary] | None:
    wage_row = effective_wage(await load_wage_rows(db, employee_id), as_of)
    if wage_row is None:
        return None
    pairs = effective_assignments(await load_assignment_rows(db, organization_id, employee_id), as_of)
    if not pairs:
        return None
    computed = compute_salary(wage_row.monthly_wage, structure_from_assignments(pairs))
    return wage_row, computed


@dataclass(frozen=True)
class SalaryComponentPatch:
    code: str
    calculation_type: CalculationType | str | None = None
    rate: Decimal | None = None
    amount: Decimal | None = None


def apply_component_updates(
    structure: list[SalaryStructureLine], updates: list[SalaryComponentPatch]
) -> list[SalaryStructureLine]:
    by_code = {line.code: line for line in structure}
    for update in updates:
        code = update.code.strip().upper()
        current = by_code.get(code)
        if current is None:
            raise PayrollError(f"Unknown salary component {code}.")
        if not line_is_editable(current.kind, current.calculation_type):
            raise PayrollError(f"{current.name} is not editable.")
        calculation_type = (
            CalculationType(update.calculation_type)
            if update.calculation_type is not None
            else CalculationType(current.calculation_type)
        )
        if not line_is_editable(current.kind, calculation_type):
            raise PayrollError(f"{current.name} is not editable.")
        rate = update.rate if update.rate is not None else current.rate
        amount = update.amount if update.amount is not None else current.amount
        if calculation_type in {CalculationType.PERCENT_OF_WAGE, CalculationType.PERCENT_OF_BASIC} and rate is None:
            raise PayrollError(f"{code} requires a rate.")
        if calculation_type is CalculationType.FIXED and amount is None:
            raise PayrollError(f"{code} requires a fixed amount.")
        by_code[code] = SalaryStructureLine(
            code=code,
            name=current.name,
            kind=current.kind,
            calculation_type=calculation_type,
            rate=rate,
            amount=amount,
        )
    return list(by_code.values())


async def _replace_open_wage(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    monthly_wage: Decimal,
    effective_from: date,
) -> EmployeeWage:
    rows = await load_wage_rows(db, employee_id)
    current = effective_wage(rows, effective_from)
    if current is not None and current.effective_from == effective_from and current.effective_to is None:
        current.monthly_wage = monthly_wage
        return current
    if current is not None and current.effective_to is None:
        if effective_from <= current.effective_from:
            current.monthly_wage = monthly_wage
            return current
        current.effective_to = effective_from - timedelta(days=1)
    wage = EmployeeWage(
        organization_id=organization_id,
        employee_id=employee_id,
        monthly_wage=monthly_wage,
        effective_from=effective_from,
        effective_to=None,
    )
    db.add(wage)
    await db.flush()
    return wage


async def _replace_open_assignment(
    db: AsyncSession,
    *,
    employee_id: UUID,
    component: SalaryComponent,
    calculation_type: str,
    rate: Decimal | None,
    amount: Decimal,
    effective_from: date,
    existing: list[EmployeeSalaryComponent],
) -> None:
    open_rows = [
        row
        for row in existing
        if row.salary_component_id == component.id and row.effective_to is None
    ]
    current = max(open_rows, key=lambda row: row.effective_from) if open_rows else None
    if current is not None and current.effective_from == effective_from:
        current.calculation_type = calculation_type
        current.rate = rate
        current.amount = amount
        return
    if current is not None:
        if effective_from <= current.effective_from:
            current.calculation_type = calculation_type
            current.rate = rate
            current.amount = amount
            return
        current.effective_to = effective_from - timedelta(days=1)
    db.add(
        EmployeeSalaryComponent(
            employee_id=employee_id,
            salary_component_id=component.id,
            calculation_type=calculation_type,
            rate=rate,
            amount=amount,
            effective_from=effective_from,
            effective_to=None,
        )
    )


async def persist_computed_salary(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    effective_from: date,
    computed: ComputedSalary,
) -> EmployeeWage:
    components = await ensure_org_components(db, organization_id)
    wage = await _replace_open_wage(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        monthly_wage=computed.monthly_wage,
        effective_from=effective_from,
    )
    existing = [
        assignment
        for assignment, _component in await load_assignment_rows(db, organization_id, employee_id)
    ]
    for line in computed.lines:
        component = components[line.code]
        await _replace_open_assignment(
            db,
            employee_id=employee_id,
            component=component,
            calculation_type=line.calculation_type.value,
            rate=line.rate,
            amount=line.amount,
            effective_from=effective_from,
            existing=existing,
        )
    await db.flush()
    return wage


async def assign_default_salary(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    effective_from: date,
    monthly_wage: Decimal = DEFAULT_MONTHLY_WAGE,
) -> ComputedSalary:
    computed = compute_salary(monthly_wage, default_salary_structure())
    await persist_computed_salary(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        effective_from=effective_from,
        computed=computed,
    )
    return computed


async def save_salary_config(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    as_of: date,
    monthly_wage: Decimal | None,
    component_updates: list[SalaryComponentPatch],
) -> tuple[EmployeeWage, ComputedSalary]:
    loaded = await load_computed_salary(db, organization_id, employee_id, as_of)
    if loaded is None:
        structure = default_salary_structure()
        wage = monthly_wage if monthly_wage is not None else DEFAULT_MONTHLY_WAGE
        effective_from = as_of
    else:
        wage_row, current = loaded
        structure = [
            SalaryStructureLine(
                code=line.code,
                name=line.name,
                kind=line.kind,
                calculation_type=line.calculation_type,
                rate=line.rate,
                amount=line.amount if line.calculation_type is CalculationType.FIXED else None,
            )
            for line in current.lines
        ]
        wage = monthly_wage if monthly_wage is not None else wage_row.monthly_wage
        effective_from = as_of
    if component_updates:
        structure = apply_component_updates(structure, component_updates)
    computed = compute_salary(money(wage), structure)
    wage_row = await persist_computed_salary(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        effective_from=effective_from,
        computed=computed,
    )
    return wage_row, computed


async def list_org_computed_salaries(
    db: AsyncSession, organization_id: UUID, as_of: date
) -> list[tuple[Employee, EmployeeWage, ComputedSalary]]:
    employees = list(
        await db.scalars(select(Employee).where(Employee.organization_id == organization_id).order_by(Employee.employee_code))
    )
    out: list[tuple[Employee, EmployeeWage, ComputedSalary]] = []
    for employee in employees:
        loaded = await load_computed_salary(db, organization_id, employee.id, as_of)
        if loaded is None:
            continue
        wage_row, computed = loaded
        out.append((employee, wage_row, computed))
    return out
