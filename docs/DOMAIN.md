# Dayflow domain

Domain model and rules for the hackathon MVP. This is not an API spec or a migration plan. Product pages and flows live in `docs/PRODUCT.md`.

## Identity and tenancy

`organizations`

- `id`, `name`, `timezone`, `currency`, `created_at`

`users`

- `id`, `email`, `password_hash`, `email_verified_at`, `status`, `last_login_at`

`organization_memberships`

- `id`, `organization_id`, `user_id`, `role` where role is `EMPLOYEE` or `HR`
- Unique on organization and user

`account_invites`

- `id`, `organization_id`, `employee_id`, `email`, `role`, `token_hash`, `expires_at`, `accepted_at`, `created_by`

## Employee record

`employees`

- `id`, `organization_id`, `user_id`, `employee_code`, `first_name`, `last_name`, `phone`, `address`, `profile_image_key`, `status`, `joined_on`, `manager_employee_id`
- Unique on organization and employee code

`job_assignments`

- `id`, `employee_id`, `title`, `department`, `employment_type`, `location`, `starts_on`, `ends_on`

`employee_documents`

- `id`, `employee_id`, `document_type`, `storage_key`, `visibility`, `uploaded_by`, `uploaded_at`
- Store file metadata and a private object-store key, not public URLs

## Attendance

`attendance_sessions`

- `id`, `employee_id`, `work_date`, `check_in_at`, `check_out_at`, `source`, `status`, `worked_minutes`
- At most one open session per employee unless split shifts are explicitly supported

`attendance_correction_requests`

- `id`, `attendance_session_id`, `requested_by`, `proposed_check_in_at`, `proposed_check_out_at`, `reason`, `status`, `reviewed_by`, `reviewed_at`, `review_comment`

`work_policies`

- `id`, `organization_id`, `timezone`, `workweek`, `full_day_minutes`, `half_day_minutes`, `late_after_local_time`

`holidays`

- `id`, `organization_id`, `name`, `date`, `location`

## Leave

`leave_types`

- `id`, `organization_id`, `name`, `code`, `is_paid`, `requires_balance`, `requires_comment`, `active`

`leave_balances`

- `id`, `employee_id`, `leave_type_id`, `period_start`, `period_end`, `granted_days`, `used_days`, `adjustment_days`

`leave_requests`

- `id`, `employee_id`, `leave_type_id`, `starts_on`, `ends_on`, `counted_days`, `reason`, `status`, `submitted_at`, `reviewed_by`, `reviewed_at`, `review_comment`

`leave_request_events`

- `id`, `leave_request_id`, `actor_user_id`, `from_status`, `to_status`, `comment`, `created_at`

## Payroll

Payroll is a monthly wage split. Domain math in `backend/app/domain/payroll.py` turns wage + structure into earning, deduction, and employer lines. Routes load, call that function, persist, and return. They do not re-encode the formula.

`employee_wages`

- `id`, `organization_id`, `employee_id`, `monthly_wage`, `effective_from`, `effective_to`
- Finalization uses the wage effective on the payroll period end date

`salary_components`

- `id`, `organization_id`, `name`, `code`, `kind` where kind is `EARNING`, `DEDUCTION`, or `EMPLOYER`, `calculation_type`, `taxable`, `active`
- `calculation_type` is `FIXED`, `PERCENT_OF_WAGE`, `PERCENT_OF_BASIC`, or `REMAINDER`
- Among earnings, only HRA may be a percentage of Basic. Employee PF may be a percentage of Basic as a deduction. Cycles and negative wage, rates, or amounts are rejected

`employee_salary_components`

- `id`, `employee_id`, `salary_component_id`, `calculation_type`, `rate`, `amount`, `effective_from`, `effective_to`
- `rate` holds a percentage (for example 50.00 is 50%). `amount` is the computed rupee value, or the configured rupee value when type is `FIXED`
- Remainder (`FIXED_ALLOW`) is computed so Basic + HRA + Standard Allowance + Performance Bonus + LTA + remainder equals monthly wage. It is not editable
- If configured earnings would exceed monthly wage, the change is rejected

`payroll_periods`

- `id`, `organization_id`, `starts_on`, `ends_on`, `pay_date`, `status`, `finalized_by`, `finalized_at`, `published_at`

`payroll_records`

- `id`, `payroll_period_id`, `employee_id`, `gross_amount`, `deduction_amount`, `net_amount`, `currency`, `payslip_storage_key`, `published_at`
- Gross is the sum of earnings, which equals monthly wage when the structure is valid
- Deduction amount is employee PF + professional tax. Employer PF is informational and does not reduce net pay
- Finalized records are immutable. A later salary change does not rewrite a snapshot

`payroll_record_lines`

- `id`, `payroll_record_id`, `salary_component_id`, `label_snapshot`, `amount`
- Finalization snapshots labels and amounts. Deduction amounts are stored signed negative

Seeded structure for the staff employee (and new hires): monthly wage ₹50,000; Basic 50% of wage; HRA 50% of Basic; Standard Allowance ₹4,167 fixed; Performance Bonus 8.33% of wage; LTA 8.33% of wage; Fixed Allowance remainder; employee PF 12% of Basic; employer PF 12% of Basic (employer line); professional tax ₹200.

HR may configure any employee's wage and editable rates or amounts. Employees may read only their own breakdown. Coworker salary stays hidden. Salary changes are org-scoped and write `audit_events`.

## Audit

`audit_events`

- `id`, `organization_id`, `actor_user_id`, `entity_type`, `entity_id`, `action`, `before_json`, `after_json`, `created_at`

Audit events are required for role changes, employee edits, attendance corrections, leave decisions, salary changes, and payroll finalization.

## Relationship sketch

```text
Organization
  ├── Membership ── User
  ├── Employee ── Job assignments
  │            ├── Documents
  │            ├── Attendance sessions ── Correction requests
  │            ├── Leave balances ── Leave type
  │            ├── Leave requests ── Leave request events
  │            ├── Salary components
  │            └── Wages
  ├── Work policies and holidays
  └── Payroll periods ── Payroll records ── Payroll record lines
```

## Business rules

1. A user cannot choose the HR role during public registration.
2. All dates and attendance calculations use the organization's timezone.
3. Check-out must be after check-in. An open session blocks another check-in unless split shifts are supported.
4. Approved leave and attendance cannot contradict each other without an HR exception.
5. Leave ranges cannot overlap another pending or approved request.
6. Rejection requires a comment. Approval records the balance used.
7. Employees can read org directory cards and coworker profiles in view-only form. They cannot edit another person's record. Attendance, leave, documents, and payroll stay self-or-HR.
8. Employees cannot edit job, role, salary, balance, attendance history, or approval fields.
9. Finalized payroll records are immutable. A correction creates a new revision or adjustment period.
10. File downloads require short-lived authorized URLs.

Implement these in `backend/app/domain`. Routes call domain functions; they do not re-encode the rules.

## Missing decisions and recommended MVP defaults

| Missing decision | Recommended MVP default |
|---|---|
| Company model | One organization per deployed demo, but keep `organization_id` in every business table |
| HR onboarding | First HR is seeded; later HR users are invite-only |
| Employee sign-up | Invite activation, not open registration |
| Password policy | Minimum 12 characters, breached-password check if available, rate-limited login |
| Forgot password | Email reset link with short expiry. Console email adapter until SMTP exists |
| Attendance source | Server timestamp; no GPS or biometric tracking |
| Multiple shifts | One attendance session per work date |
| Late and half-day rules | Organization policy with seeded values |
| Corrections | Employee requests, HR decides, audit event always recorded |
| Weekends and holidays | Excluded from leave day count by policy |
| Leave cancellation | Employee can cancel pending requests; approved leave needs HR reversal |
| Payroll engine | Monthly wage split with PF (12% of Basic) and professional tax ₹200; no broader tax engine |
| Payslip | Generated only after HR finalizes and publishes a period |
| Documents | Private storage with HR/self access, size and type limits. Tab may stay deferred |
| Notifications | In-app activity only; email stays future work except account security |
| Reports | Defer analytics. CSV export only if time remains |

## Non-functional baseline

- Authorization checks on every server query and mutation.
- Password hashing with Argon2id and rate-limited authentication.
- Organization data isolation.
- Audit history for privileged changes.
- Accessible keyboard navigation, visible focus, labels, and status text.
- Responsive layouts down to a 360 px employee viewport. Admin tables can use a 1024 px minimum desktop workspace.
- Pagination or cursor loading for employee, attendance, leave, and payroll lists.
- Idempotent approve, reject, check-in, check-out, and payroll finalization operations.
- Transactions for leave approval and payroll finalization.
- Private documents and payslips with authorized, expiring download links.

Hackathon schema creation: `Base.metadata.create_all` on API startup. That is not a migration plan. Introduce Alembic when the schema has survived the first real features.
