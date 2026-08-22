from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentPrincipal, get_current_principal, require_hr
from app.core.db import get_db
from app.domain.payroll import (
    PayrollError,
    PayrollPeriodStatus,
    assert_can_finalize,
    assert_can_publish,
    assert_mutable,
    signed_line_amount,
    totals_from_components,
)
from app.domain.roles import Role
from app.models import (
    AuditEvent,
    Employee,
    EmployeeSalaryComponent,
    Organization,
    PayrollPeriod,
    PayrollRecord,
    PayrollRecordLine,
    SalaryComponent,
)
from app.schemas.payroll import (
    PayrollPeriodActionOut,
    PayrollRecordDetailOut,
    PayrollRecordLineOut,
    SalaryComponentOut,
    SalaryComponentPatchRequest,
    SalaryComponentPatchResponse,
)

router = APIRouter(prefix="/payroll", tags=["payroll"])


def _raise_payroll(exc: PayrollError, *, conflict: bool = False) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT if conflict else status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    ) from exc


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


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


async def _salary_components_out(
    db: AsyncSession, organization_id: UUID, employee_id: UUID
) -> list[SalaryComponentOut]:
    rows = (
        await db.execute(
            select(EmployeeSalaryComponent, SalaryComponent)
            .join(SalaryComponent, SalaryComponent.id == EmployeeSalaryComponent.salary_component_id)
            .where(
                EmployeeSalaryComponent.employee_id == employee_id,
                SalaryComponent.organization_id == organization_id,
            )
            .order_by(SalaryComponent.code)
        )
    ).all()
    return [
        SalaryComponentOut(
            code=component.code,
            name=component.name,
            kind=component.kind,
            amount=assignment.amount,
        )
        for assignment, component in rows
    ]


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
    return {
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


@router.patch("/salary-components", response_model=SalaryComponentPatchResponse)
async def patch_salary_components(
    body: SalaryComponentPatchRequest,
    principal: CurrentPrincipal = Depends(require_hr),
    db: AsyncSession = Depends(get_db),
) -> SalaryComponentPatchResponse:
    period = await _org_period(db, principal.organization_id, body.period_id)
    try:
        assert_mutable(PayrollPeriodStatus(period.status))
    except PayrollError as exc:
        _raise_payroll(exc, conflict=True)
    await _org_employee(db, principal.organization_id, body.employee_id)
    if not body.components:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one salary component is required.")

    for item in body.components:
        component = await db.scalar(
            select(SalaryComponent).where(
                SalaryComponent.organization_id == principal.organization_id,
                SalaryComponent.code == item.code.strip().upper(),
                SalaryComponent.active.is_(True),
            )
        )
        if component is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown salary component {item.code}.",
            )
        assignment = await db.scalar(
            select(EmployeeSalaryComponent).where(
                EmployeeSalaryComponent.employee_id == body.employee_id,
                EmployeeSalaryComponent.salary_component_id == component.id,
            )
        )
        amount = item.amount.quantize(Decimal("0.01"))
        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No {component.code} assignment for this employee.",
            )
        before = {"code": component.code, "amount": _money(assignment.amount)}
        assignment.amount = amount
        db.add(
            AuditEvent(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                entity_type="employee_salary_component",
                entity_id=str(assignment.id),
                action="payroll.salary.update",
                before_json=before,
                after_json={"code": component.code, "amount": _money(amount)},
            )
        )

    await db.commit()
    return SalaryComponentPatchResponse(
        employee_id=body.employee_id,
        components=await _salary_components_out(db, principal.organization_id, body.employee_id),
    )


async def _period_assignments(
    db: AsyncSession, organization_id: UUID
) -> dict[UUID, list[tuple[EmployeeSalaryComponent, SalaryComponent]]]:
    rows = (
        await db.execute(
            select(EmployeeSalaryComponent, SalaryComponent, Employee)
            .join(SalaryComponent, SalaryComponent.id == EmployeeSalaryComponent.salary_component_id)
            .join(Employee, Employee.id == EmployeeSalaryComponent.employee_id)
            .where(
                Employee.organization_id == organization_id,
                SalaryComponent.organization_id == organization_id,
                SalaryComponent.active.is_(True),
            )
            .order_by(Employee.employee_code, SalaryComponent.code)
        )
    ).all()
    grouped: dict[UUID, list[tuple[EmployeeSalaryComponent, SalaryComponent]]] = {}
    for assignment, component, employee in rows:
        grouped.setdefault(employee.id, []).append((assignment, component))
    return grouped


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
    grouped = await _period_assignments(db, principal.organization_id)
    snapshots: list[tuple[UUID, Decimal, Decimal, Decimal, list[tuple[SalaryComponent, Decimal]]]] = []
    period_net = Decimal("0.00")
    for employee_id, assignments in grouped.items():
        items = [(component.kind, assignment.amount) for assignment, component in assignments]
        gross, deductions, net = totals_from_components(items)
        try:
            assert_can_finalize(status=PayrollPeriodStatus(period.status), net=net)
        except PayrollError as exc:
            _raise_payroll(exc, conflict=True)
        period_net += net
        lines = [
            (component, signed_line_amount(component.kind, assignment.amount))
            for assignment, component in assignments
        ]
        snapshots.append((employee_id, gross, deductions, net, lines))
    if not snapshots:
        try:
            assert_can_finalize(status=PayrollPeriodStatus(period.status), net=Decimal("0.00"))
        except PayrollError as exc:
            _raise_payroll(exc, conflict=True)

    existing_ids = list(
        await db.scalars(select(PayrollRecord.id).where(PayrollRecord.payroll_period_id == period.id))
    )
    if existing_ids:
        await db.execute(delete(PayrollRecordLine).where(PayrollRecordLine.payroll_record_id.in_(existing_ids)))
        await db.execute(delete(PayrollRecord).where(PayrollRecord.id.in_(existing_ids)))

    now = datetime.now(UTC)
    record_outs: list[PayrollRecordDetailOut] = []
    for employee_id, gross, deductions, net, lines in snapshots:
        record = PayrollRecord(
            payroll_period_id=period.id,
            employee_id=employee_id,
            gross_amount=gross,
            deduction_amount=deductions,
            net_amount=net,
            currency=org.currency,
            published_at=None,
        )
        db.add(record)
        await db.flush()
        line_outs: list[PayrollRecordLineOut] = []
        for component, amount in lines:
            db.add(
                PayrollRecordLine(
                    payroll_record_id=record.id,
                    salary_component_id=component.id,
                    label_snapshot=component.name,
                    amount=amount,
                )
            )
            line_outs.append(
                PayrollRecordLineOut(code=component.code, label=component.name, amount=amount)
            )
        record_outs.append(
            PayrollRecordDetailOut(
                id=record.id,
                employee_id=employee_id,
                gross_amount=gross,
                deduction_amount=deductions,
                net_amount=net,
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
            if line.salary_component_id is not None:
                component = await db.get(SalaryComponent, line.salary_component_id)
                if component is not None:
                    code = component.code
            line_outs.append(
                PayrollRecordLineOut(code=code, label=line.label_snapshot, amount=line.amount)
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
