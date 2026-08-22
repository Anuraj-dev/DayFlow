from datetime import UTC, date, datetime
from decimal import Decimal
from html import escape
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
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
from app.domain.attendance import (
    AttendanceStatus,
    CorrectionStatus,
    leave_dates_on_scheduled,
    payable_summary_for_employee,
    scheduled_dates,
)
from app.domain.payroll import (
    CalculationType,
    ComponentKind,
    ComputedSalary,
    PayrollError,
    PayrollPeriodStatus,
    assert_can_finalize,
    assert_can_publish,
    assert_no_attendance_blockers,
    prorate_computed_salary,
    signed_line_amount,
)
from app.domain.roles import Role
from app.models import (
    AttendanceCorrectionRequest,
    AttendanceSession,
    AuditEvent,
    Employee,
    Holiday,
    LeaveRequest,
    LeaveType,
    Organization,
    PayrollPeriod,
    PayrollRecord,
    PayrollRecordLine,
    SalaryComponent,
    WorkPolicy,
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


def _payslip_html(
    *,
    organization: Organization,
    employee: Employee,
    period: PayrollPeriod,
    record: PayrollRecord,
    lines: list[PayrollRecordLine],
) -> str:
    employee_name = escape(f"{employee.first_name} {employee.last_name}")
    organization_name = escape(organization.name)
    employee_code = escape(employee.employee_code)
    currency = escape(record.currency)
    line_rows = "".join(
        f"<tr><td>{escape(line.label_snapshot)}</td><td class='amount'>{currency} {_money(line.amount)}</td></tr>"
        for line in lines
    )
    if not line_rows:
        line_rows = "<tr><td colspan='2' class='muted'>No component breakdown is available.</td></tr>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Payslip - {employee_name}</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; color: #1f2937; }}
    body {{ margin: 0; background: #f3f4f6; }}
    main {{ max-width: 760px; margin: 32px auto; padding: 36px; background: white; border: 1px solid #d1d5db; }}
    header {{ display: flex; justify-content: space-between; gap: 24px; border-bottom: 2px solid #714b67; padding-bottom: 20px; }}
    h1, h2, p {{ margin-top: 0; }}
    h1 {{ margin-bottom: 6px; font-size: 28px; }}
    h2 {{ margin: 28px 0 10px; font-size: 18px; }}
    .muted {{ color: #6b7280; }}
    .meta {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px 24px; margin-top: 24px; }}
    .meta div {{ border-bottom: 1px solid #e5e7eb; padding: 8px 0; }}
    .meta strong {{ display: block; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
    .amount {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .totals {{ margin: 24px 0 0 auto; width: min(100%, 360px); }}
    .totals div {{ display: flex; justify-content: space-between; padding: 8px; }}
    .net {{ border-top: 2px solid #714b67; font-size: 20px; font-weight: 700; }}
    .actions {{ max-width: 760px; margin: 20px auto; text-align: right; }}
    button {{ border: 0; border-radius: 4px; padding: 10px 18px; background: #714b67; color: white; cursor: pointer; }}
    @media (max-width: 640px) {{ main {{ margin: 0; padding: 24px; }} .meta {{ grid-template-columns: 1fr; }} }}
    @media print {{ body {{ background: white; }} main {{ max-width: none; margin: 0; border: 0; }} .actions {{ display: none; }} }}
  </style>
</head>
<body>
  <div class="actions"><button type="button" onclick="window.print()">Print or save as PDF</button></div>
  <main>
    <header>
      <div><h1>{organization_name}</h1><p class="muted">Employee payslip</p></div>
      <div><strong>Pay date</strong><p>{period.pay_date.strftime('%d %b %Y')}</p></div>
    </header>
    <section class="meta" aria-label="Payslip details">
      <div><span class="muted">Employee</span><strong>{employee_name}</strong></div>
      <div><span class="muted">Employee ID</span><strong>{employee_code}</strong></div>
      <div><span class="muted">Pay period</span><strong>{period.starts_on.strftime('%d %b %Y')} - {period.ends_on.strftime('%d %b %Y')}</strong></div>
      <div><span class="muted">Payable days</span><strong>{_money(record.payable_days) if record.payable_days is not None else '-'}</strong></div>
    </section>
    <h2>Pay components</h2>
    <table><thead><tr><th>Component</th><th class="amount">Amount</th></tr></thead><tbody>{line_rows}</tbody></table>
    <section class="totals" aria-label="Pay totals">
      <div><span>Gross pay</span><strong>{currency} {_money(record.gross_amount)}</strong></div>
      <div><span>Deductions</span><strong>{currency} {_money(record.deduction_amount)}</strong></div>
      <div class="net"><span>Net pay</span><span>{currency} {_money(record.net_amount)}</span></div>
    </section>
  </main>
</body>
</html>"""


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
                "payroll_period_id": str(record.payroll_period_id),
                "gross_amount": _money(record.gross_amount),
                "deduction_amount": _money(record.deduction_amount),
                "net_amount": _money(record.net_amount),
                "currency": record.currency,
                "published_at": record.published_at.isoformat() if record.published_at else None,
                "scheduled_days": _money(record.scheduled_days) if record.scheduled_days is not None else None,
                "payable_days": _money(record.payable_days) if record.payable_days is not None else None,
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


@router.get("/records/{record_id}/payslip", response_class=HTMLResponse)
async def download_payslip(
    record_id: UUID,
    principal: CurrentPrincipal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    record = await db.scalar(
        select(PayrollRecord)
        .join(PayrollPeriod)
        .where(
            PayrollRecord.id == record_id,
            PayrollPeriod.organization_id == principal.organization_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payslip not found.")
    if principal.role is Role.EMPLOYEE and (
        principal.employee_id != record.employee_id or record.published_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only your published payslips are available.",
        )

    employee = await _org_employee(db, principal.organization_id, record.employee_id)
    period = await _org_period(db, principal.organization_id, record.payroll_period_id)
    organization = await db.get(Organization, principal.organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")
    lines = list(
        await db.scalars(
            select(PayrollRecordLine)
            .where(PayrollRecordLine.payroll_record_id == record.id)
            .order_by(PayrollRecordLine.created_at, PayrollRecordLine.id)
        )
    )
    safe_employee_code = "".join(
        character for character in employee.employee_code if character.isalnum() or character in "-_"
    ) or str(employee.id)
    filename = f"payslip-{safe_employee_code}-{period.starts_on:%Y-%m}.html"
    return HTMLResponse(
        _payslip_html(
            organization=organization,
            employee=employee,
            period=period,
            record=record,
            lines=lines,
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


async def _period_work_calendar(
    db: AsyncSession, organization_id: UUID, starts_on: date, ends_on: date
) -> tuple[list[date], set[date]]:
    policy = await db.scalar(select(WorkPolicy).where(WorkPolicy.organization_id == organization_id))
    workweek = policy.workweek if policy and policy.workweek else [0, 1, 2, 3, 4]
    holidays = set(await db.scalars(select(Holiday.date).where(Holiday.organization_id == organization_id)))
    scheduled = scheduled_dates(starts_on, ends_on, workweek=workweek, holidays=holidays)
    return scheduled, set(scheduled)


async def _attendance_blockers(
    db: AsyncSession, organization_id: UUID, starts_on: date, ends_on: date
) -> tuple[int, int]:
    open_session_count = len(
        list(
            await db.scalars(
                select(AttendanceSession.id)
                .join(Employee, Employee.id == AttendanceSession.employee_id)
                .where(
                    Employee.organization_id == organization_id,
                    AttendanceSession.status == AttendanceStatus.OPEN.value,
                    AttendanceSession.check_out_at.is_(None),
                    AttendanceSession.work_date >= starts_on,
                    AttendanceSession.work_date <= ends_on,
                )
            )
        )
    )
    pending_correction_count = len(
        list(
            await db.scalars(
                select(AttendanceCorrectionRequest.id)
                .join(
                    AttendanceSession,
                    AttendanceSession.id == AttendanceCorrectionRequest.attendance_session_id,
                )
                .join(Employee, Employee.id == AttendanceSession.employee_id)
                .where(
                    Employee.organization_id == organization_id,
                    AttendanceCorrectionRequest.status == CorrectionStatus.PENDING.value,
                    AttendanceSession.work_date >= starts_on,
                    AttendanceSession.work_date <= ends_on,
                )
            )
        )
    )
    return open_session_count, pending_correction_count


async def _period_leave_dates(
    db: AsyncSession,
    organization_id: UUID,
    scheduled: set[date],
    starts_on: date,
    ends_on: date,
) -> tuple[dict[UUID, set[date]], dict[UUID, set[date]]]:
    rows = (
        await db.execute(
            select(LeaveRequest.employee_id, LeaveRequest.starts_on, LeaveRequest.ends_on, LeaveType.is_paid)
            .join(LeaveType, LeaveType.id == LeaveRequest.leave_type_id)
            .join(Employee, Employee.id == LeaveRequest.employee_id)
            .where(
                Employee.organization_id == organization_id,
                LeaveRequest.status == "APPROVED",
                LeaveRequest.starts_on <= ends_on,
                LeaveRequest.ends_on >= starts_on,
            )
        )
    ).all()
    paid: dict[UUID, set[date]] = {}
    unpaid: dict[UUID, set[date]] = {}
    for employee_id, leave_start, leave_end, is_paid in rows:
        covered = leave_dates_on_scheduled(leave_start, leave_end, scheduled=scheduled)
        target = paid if is_paid else unpaid
        target.setdefault(employee_id, set()).update(covered)
    return paid, unpaid


async def _period_session_status(
    db: AsyncSession, organization_id: UUID, starts_on: date, ends_on: date
) -> dict[tuple[UUID, date], str]:
    rows = list(
        await db.scalars(
            select(AttendanceSession)
            .join(Employee, Employee.id == AttendanceSession.employee_id)
            .where(
                Employee.organization_id == organization_id,
                AttendanceSession.work_date >= starts_on,
                AttendanceSession.work_date <= ends_on,
            )
            .order_by(AttendanceSession.check_in_at)
        )
    )
    by_day: dict[tuple[UUID, date], str] = {}
    for row in rows:
        by_day[(row.employee_id, row.work_date)] = row.status
    return by_day


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
        open_session_count, pending_correction_count = await _attendance_blockers(
            db, principal.organization_id, period.starts_on, period.ends_on
        )
        assert_no_attendance_blockers(
            open_session_count=open_session_count,
            pending_correction_count=pending_correction_count,
        )
    except PayrollError as exc:
        _raise_payroll(exc, conflict=True)

    scheduled, scheduled_set = await _period_work_calendar(
        db, principal.organization_id, period.starts_on, period.ends_on
    )
    paid_leave, unpaid_leave = await _period_leave_dates(
        db, principal.organization_id, scheduled_set, period.starts_on, period.ends_on
    )
    session_status = await _period_session_status(
        db, principal.organization_id, period.starts_on, period.ends_on
    )

    components = {
        component.code.upper(): component
        for component in (
            await db.scalars(
                select(SalaryComponent).where(SalaryComponent.organization_id == principal.organization_id)
            )
        ).all()
    }
    snapshots: list[
        tuple[UUID, ComputedSalary, Decimal, Decimal, list[tuple[SalaryComponent | None, Decimal, str, str]]]
    ] = []
    period_net = Decimal("0.00")
    try:
        for employee, _wage, computed in await list_org_computed_salaries(
            db, principal.organization_id, period.ends_on
        ):
            employee_sessions = {
                day: status
                for (owner_id, day), status in session_status.items()
                if owner_id == employee.id
            }
            totals = payable_summary_for_employee(
                scheduled=scheduled,
                session_status_by_date=employee_sessions,
                paid_leave_dates=paid_leave.get(employee.id, set()),
                unpaid_leave_dates=unpaid_leave.get(employee.id, set()),
            )
            prorated = prorate_computed_salary(
                computed,
                payable_days=totals.payable_days,
                scheduled_days=totals.scheduled_days,
            )
            assert_can_finalize(status=PayrollPeriodStatus(period.status), net=prorated.net_amount)
            period_net += prorated.net_amount
            lines = []
            for line in prorated.lines:
                component = components.get(line.code)
                lines.append(
                    (
                        component,
                        signed_line_amount(line.kind, line.amount),
                        line.name,
                        line.kind.value,
                    )
                )
            snapshots.append((employee.id, prorated, totals.scheduled_days, totals.payable_days, lines))
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
    for employee_id, computed, scheduled_days, payable_days, lines in snapshots:
        record = PayrollRecord(
            payroll_period_id=period.id,
            employee_id=employee_id,
            gross_amount=computed.gross_amount,
            deduction_amount=computed.deduction_amount,
            net_amount=computed.net_amount,
            currency=org.currency,
            published_at=None,
            scheduled_days=scheduled_days,
            payable_days=payable_days,
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
                scheduled_days=scheduled_days,
                payable_days=payable_days,
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
                scheduled_days=record.scheduled_days,
                payable_days=record.payable_days,
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
