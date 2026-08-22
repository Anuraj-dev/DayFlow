from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.salary import (
    SalaryComponentPatch,
    list_org_computed_salaries,
    load_computed_salary,
    save_salary_config,
)
from app.api.deps import CurrentPrincipal, get_current_principal, require_hr
from app.core.db import get_db
from app.domain.payroll import (
    CalculationType,
    ComponentKind,
    ComputedSalary,
    PayrollError,
    PayrollPeriodStatus,
    assert_can_finalize,
    assert_can_publish,
    signed_line_amount,
)
from app.domain.roles import Role
from app.models import (
    AuditEvent,
    Employee,
    Organization,
    PayrollPeriod,
    PayrollRecord,
    PayrollRecordLine,
    SalaryComponent,
)
from app.schemas.payroll import (
    EmployeeSalaryInputsOut,
    EmployeeSalaryOut,
    EmployeeSalaryPatchRequest,
    PayrollPeriodActionOut,
    PayrollRecordDetailOut,
    PayrollRecordLineOut,
    SalaryLineOut,
)

router = APIRouter(prefix="/payroll", tags=["payroll"])


def _raise_payroll(exc: PayrollError, *, conflict: bool = False) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT if conflict else status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    ) from exc


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def _org_today(org: Organization | None) -> date:
    timezone_name = org.timezone if org and org.timezone else "UTC"
    return datetime.now(UTC).astimezone(ZoneInfo(timezone_name)).date()


async def _org_period(db: AsyncSession, organization_id: UUID, period_id: UUID) -> PayrollPeriod:
    period = await db.scalar(
        select(PayrollPeriod).where(
            PayrollPeriod.id == period_id,
            PayrollPeriod.organization_id == organization_id,
        )
    )
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll period not found.")
    return period


async def _org_employee(db: AsyncSession, organization_id: UUID, employee_id: UUID) -> Employee:
    employee = await db.scalar(
        select(Employee).where(
            Employee.id == employee_id,
            Employee.organization_id == organization_id,
        )
    )
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found.")
    return employee


def _can_read_salary(principal: CurrentPrincipal, employee_id: UUID) -> bool:
    if principal.role is Role.HR:
        return True
    return principal.employee_id is not None and principal.employee_id == employee_id


def _line_out(line) -> SalaryLineOut:
    return SalaryLineOut(
        code=line.code,
        name=line.name,
        kind=line.kind.value if isinstance(line.kind, ComponentKind) else str(line.kind),
        calculation_type=(
            line.calculation_type.value
            if isinstance(line.calculation_type, CalculationType)
            else str(line.calculation_type)
        ),
        rate=line.rate,
        amount=line.amount,
        editable=line.editable,
    )


def _salary_out(employee_id: UUID, currency: str, effective_from, computed: ComputedSalary) -> EmployeeSalaryOut:
    return EmployeeSalaryOut(
        employee_id=employee_id,
        monthly_wage=computed.monthly_wage,
        currency=currency,
        effective_from=effective_from,
        gross_amount=computed.gross_amount,
        deduction_amount=computed.deduction_amount,
        net_amount=computed.net_amount,
        employer_amount=computed.employer_amount,
        lines=[_line_out(line) for line in computed.lines],
    )


def _salary_audit(computed: ComputedSalary, effective_from) -> dict:
    return {
        "monthly_wage": _money(computed.monthly_wage),
        "effective_from": effective_from.isoformat(),
        "lines": [
            {
                "code": line.code,
                "calculation_type": line.calculation_type.value,
                "rate": _money(line.rate) if line.rate is not None else None,
                "amount": _money(line.amount),
            }
            for line in computed.lines
        ],
    }


async def _currency(db: AsyncSession, organization_id: UUID) -> str:
    org = await db.get(Organization, organization_id)
    return org.currency if org is not None else "INR"


@router.get("")
async def payroll_home(
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> dict:
    periods_query = (
        select(PayrollPeriod)
        .where(PayrollPeriod.organization_id == principal.organization_id)
        .order_by(PayrollPeriod.starts_on.desc())
    )
    if principal.role is Role.EMPLOYEE:
        periods_query = periods_query.where(PayrollPeriod.status == PayrollPeriodStatus.PUBLISHED.value)
    periods = list(await db.scalars(periods_query))
    records_query = select(PayrollRecord).join(PayrollPeriod).where(
        PayrollPeriod.organization_id == principal.organization_id
    )
    if principal.role is Role.EMPLOYEE:
        if principal.employee_id is None:
            records_query = records_query.where(False)
        else:
            records_query = records_query.where(
                PayrollRecord.employee_id == principal.employee_id,
                PayrollRecord.published_at.is_not(None),
            )
    records = list(await db.scalars(records_query))
    payload: dict = {
        "role": principal.role.value,
        "periods": [
            {
                "id": str(period.id),
                "starts_on": period.starts_on.isoformat(),
                "ends_on": period.ends_on.isoformat(),
                "pay_date": period.pay_date.isoformat(),
                "status": period.status,
            }
            for period in periods
        ],
        "records": [
            {
                "id": str(record.id),
                "employee_id": str(record.employee_id),
                "net_amount": _money(record.net_amount),
                "currency": record.currency,
                "published_at": record.published_at.isoformat() if record.published_at else None,
            }
            for record in records
        ],
    }
    if principal.role is Role.HR:
        org = await db.get(Organization, principal.organization_id)
        as_of = _org_today(org)
        currency = org.currency if org is not None else "INR"
        salary_inputs: list[EmployeeSalaryInputsOut] = []
        for employee, _wage, computed in await list_org_computed_salaries(
            db, principal.organization_id, as_of
        ):
            salary_inputs.append(
                EmployeeSalaryInputsOut(
                    employee_id=employee.id,
                    employee_name=f"{employee.first_name} {employee.last_name}",
                    monthly_wage=computed.monthly_wage,
                    net_amount=computed.net_amount,
                    components=[_line_out(line) for line in computed.lines],
                )
            )
        payload["salary_inputs"] = [row.model_dump(mode="json") for row in salary_inputs]
        payload["currency"] = currency
    return payload


@router.get("/employees/{employee_id}/salary", response_model=EmployeeSalaryOut)
async def get_employee_salary(
    employee_id: UUID,
    as_of: date | None = Query(default=None),
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> EmployeeSalaryOut:
    employee = await _org_employee(db, principal.organization_id, employee_id)
    if not _can_read_salary(principal, employee.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Salary is visible only to HR or the employee.",
        )
    org = await db.get(Organization, principal.organization_id)
    on_date = as_of or _org_today(org)
    loaded = await load_computed_salary(db, principal.organization_id, employee.id, on_date)
    if loaded is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary is not configured.")
    wage_row, computed = loaded
    return _salary_out(employee.id, org.currency if org is not None else "INR", wage_row.effective_from, computed)


@router.patch("/employees/{employee_id}/salary", response_model=EmployeeSalaryOut)
async def patch_employee_salary(
    employee_id: UUID,
    body: EmployeeSalaryPatchRequest,
    principal: CurrentPrincipal = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
) -> EmployeeSalaryOut:
    employee = await _org_employee(db, principal.organization_id, employee_id)
    if body.monthly_wage is None and not body.components:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A monthly wage or at least one salary component is required.",
        )
    org = await db.get(Organization, principal.organization_id)
    as_of = body.effective_from or _org_today(org)
    before_loaded = await load_computed_salary(db, principal.organization_id, employee.id, as_of)
    before = (
        _salary_audit(before_loaded[1], before_loaded[0].effective_from) if before_loaded is not None else None
    )
    updates = [
        SalaryComponentPatch(
            code=item.code,
            calculation_type=item.calculation_type,
            rate=item.rate,
            amount=item.amount,
        )
        for item in (body.components or [])
    ]
    try:
        wage_row, computed = await save_salary_config(
            db,
            organization_id=principal.organization_id,
            employee_id=employee.id,
            as_of=as_of,
            monthly_wage=body.monthly_wage,
            component_updates=updates,
        )
    except PayrollError as exc:
        _raise_payroll(exc)
    db.add(
        AuditEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            entity_type="employee_salary",
            entity_id=str(employee.id),
            action="payroll.salary.update",
            before_json=before,
            after_json=_salary_audit(computed, wage_row.effective_from),
        )
    )
    await db.commit()
    return _salary_out(
        employee.id,
        org.currency if org is not None else "INR",
        wage_row.effective_from,
        computed,
    )


def _period_action_out(period: PayrollPeriod, records: list[PayrollRecordDetailOut]) -> PayrollPeriodActionOut:
    return PayrollPeriodActionOut(
        id=period.id,
        starts_on=period.starts_on,
        ends_on=period.ends_on,
        pay_date=period.pay_date,
        status=period.status,
        records=records,
    )


@router.post("/periods/{period_id}/finalize", response_model=PayrollPeriodActionOut)
async def finalize_period(
    period_id: UUID,
    principal: CurrentPrincipal = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
) -> PayrollPeriodActionOut:
    period = await _org_period(db, principal.organization_id, period_id)
    org = await db.get(Organization, principal.organization_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    try:
        assert_can_finalize(status=PayrollPeriodStatus(period.status), net=Decimal("0.00"))
    except PayrollError as exc:
        _raise_payroll(exc, conflict=True)

    components = {
        component.code.upper(): component
        for component in (
            await db.scalars(
                select(SalaryComponent).where(SalaryComponent.organization_id == principal.organization_id)
            )
        ).all()
    }
    snapshots: list[tuple[UUID, ComputedSalary, list[tuple[SalaryComponent | None, Decimal, str, str]]]] = []
    period_net = Decimal("0.00")
    try:
        for employee, _wage, computed in await list_org_computed_salaries(
            db, principal.organization_id, period.ends_on
        ):
            assert_can_finalize(status=PayrollPeriodStatus(period.status), net=computed.net_amount)
            period_net += computed.net_amount
            lines = []
            for line in computed.lines:
                component = components.get(line.code)
                lines.append(
                    (
                        component,
                        signed_line_amount(line.kind, line.amount),
                        line.name,
                        line.kind.value,
                    )
                )
            snapshots.append((employee.id, computed, lines))
    except PayrollError as exc:
        _raise_payroll(exc, conflict=str(exc) == "Only a draft payroll period can be finalized.")

    existing_ids = list(
        await db.scalars(select(PayrollRecord.id).where(PayrollRecord.payroll_period_id == period.id))
    )
    if existing_ids:
        await db.execute(delete(PayrollRecordLine).where(PayrollRecordLine.payroll_record_id.in_(existing_ids)))
        await db.execute(delete(PayrollRecord).where(PayrollRecord.id.in_(existing_ids)))

    now = datetime.now(UTC)
    record_outs: list[PayrollRecordDetailOut] = []
    for employee_id, computed, lines in snapshots:
        record = PayrollRecord(
            payroll_period_id=period.id,
            employee_id=employee_id,
            gross_amount=computed.gross_amount,
            deduction_amount=computed.deduction_amount,
            net_amount=computed.net_amount,
            currency=org.currency,
            published_at=None,
        )
        db.add(record)
        await db.flush()
        line_outs: list[PayrollRecordLineOut] = []
        for component, amount, label, kind in lines:
            db.add(
                PayrollRecordLine(
                    payroll_record_id=record.id,
                    salary_component_id=component.id if component is not None else None,
                    label_snapshot=label,
                    amount=amount,
                )
            )
            line_outs.append(
                PayrollRecordLineOut(
                    code=component.code if component is not None else "",
                    label=label,
                    amount=amount,
                    kind=kind,
                )
            )
        record_outs.append(
            PayrollRecordDetailOut(
                id=record.id,
                employee_id=employee_id,
                gross_amount=computed.gross_amount,
                deduction_amount=computed.deduction_amount,
                net_amount=computed.net_amount,
                currency=org.currency,
                published_at=None,
                lines=line_outs,
            )
        )

    before = {"status": period.status}
    period.status = PayrollPeriodStatus.FINALIZED.value
    period.finalized_by = principal.user_id
    period.finalized_at = now
    db.add(
        AuditEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            entity_type="payroll_period",
            entity_id=str(period.id),
            action="payroll.period.finalize",
            before_json=before,
            after_json={"status": period.status, "net_amount": _money(period_net)},
        )
    )
    await db.commit()
    return _period_action_out(period, record_outs)


async def _record_details(db: AsyncSession, period_id: UUID) -> list[PayrollRecordDetailOut]:
    records = list(
        await db.scalars(
            select(PayrollRecord)
            .where(PayrollRecord.payroll_period_id == period_id)
            .order_by(PayrollRecord.employee_id)
        )
    )
    details: list[PayrollRecordDetailOut] = []
    for record in records:
        lines = list(
            await db.scalars(
                select(PayrollRecordLine).where(PayrollRecordLine.payroll_record_id == record.id)
            )
        )
        line_outs: list[PayrollRecordLineOut] = []
        for line in lines:
            code = ""
            kind = None
            if line.salary_component_id is not None:
                component = await db.get(SalaryComponent, line.salary_component_id)
                if component is not None:
                    code = component.code
                    kind = component.kind
            line_outs.append(
                PayrollRecordLineOut(code=code, label=line.label_snapshot, amount=line.amount, kind=kind)
            )
        details.append(
            PayrollRecordDetailOut(
                id=record.id,
                employee_id=record.employee_id,
                gross_amount=record.gross_amount,
                deduction_amount=record.deduction_amount,
                net_amount=record.net_amount,
                currency=record.currency,
                published_at=record.published_at,
                lines=line_outs,
            )
        )
    return details


@router.post("/periods/{period_id}/publish", response_model=PayrollPeriodActionOut)
async def publish_period(
    period_id: UUID,
    principal: CurrentPrincipal = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
) -> PayrollPeriodActionOut:
    period = await _org_period(db, principal.organization_id, period_id)
    try:
        assert_can_publish(PayrollPeriodStatus(period.status))
    except PayrollError as exc:
        _raise_payroll(exc, conflict=True)
    now = datetime.now(UTC)
    records = list(
        await db.scalars(select(PayrollRecord).where(PayrollRecord.payroll_period_id == period.id))
    )
    before = {"status": period.status}
    period.status = PayrollPeriodStatus.PUBLISHED.value
    period.published_at = now
    for record in records:
        record.published_at = now
    db.add(
        AuditEvent(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            entity_type="payroll_period",
            entity_id=str(period.id),
            action="payroll.period.publish",
            before_json=before,
            after_json={"status": period.status, "published_at": now.isoformat()},
        )
    )
    await db.commit()
    return _period_action_out(period, await _record_details(db, period.id))
