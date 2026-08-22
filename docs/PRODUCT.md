# Dayflow product

Hackathon MVP for a small-company HR operations app. Build against this page when adding routes, states, navigation, or visual treatment. Domain tables and rules live in `docs/DOMAIN.md`.

## The short answer

Build **9 route templates** for the minimum credible MVP. Design **12 hi-fi frames** because dashboard, attendance, time-off, and payroll expose different employee and HR states.

The 9 routes:

1. `/sign-in`
2. `/activate-account`
3. `/dashboard`
4. `/employees`
5. `/employees/:employeeId`
6. `/attendance`
7. `/time-off`
8. `/payroll`
9. `/settings` for HR policy configuration

`/settings` can stay unimplemented if policy values are seeded. That leaves **8 implemented route templates** as the demo floor. Do not remove account activation, permission checks, or the role-specific states.

The 12 design frames:

1. Sign in
2. Account activation and email verification state
3. Employee dashboard
4. HR dashboard
5. People directory
6. Employee profile
7. Employee attendance
8. HR attendance review
9. Employee time off
10. HR leave approvals
11. Employee payroll
12. HR payroll control

## What the app is

Employees maintain a profile, record attendance, request leave, and read payroll. HR officers manage employee records, review attendance, approve leave, and maintain payroll data.

The useful center is the daily loop:

1. An employee checks in.
2. Dayflow records the work session.
3. Leave changes the expected attendance state.
4. HR reviews exceptions instead of scanning every record.
5. Approved attendance and leave feed the payroll period.

That flow shapes navigation and the data model.

## Source analysis

### Confirmed by the source PDF

- Authentication includes sign-up, sign-in, password rules, and email verification.
- Two user classes: employee and Admin/HR Officer.
- Employees can view personal, job, salary, document, and profile-picture data.
- Employees can edit address, phone, and profile picture. HR can edit all employee data.
- Attendance has daily and weekly views, check-in/out, and Present, Absent, Half-day, and Leave states.
- Employees see only their own attendance. HR can see all attendance.
- Employees can request paid, sick, or unpaid leave for a date range with remarks.
- HR can approve or reject leave and add comments.
- Employees have read-only payroll access. HR can view all payroll and update salary structure.
- Notifications and reports are marked as future work.

### Existing Excalidraw board

Keep visible attendance status, compact profile tabs, and a single time-off workspace. Correct the role structure: an employee lands on a personal dashboard, not the company directory. The directory, other people's salary data, approval buttons, and payroll editing are HR-only.

### Problems in the source material

- The PDF lets users choose Employee or HR during sign-up. That is a privilege-escalation bug. HR comes from an invitation or an existing HR administrator.
- Non-functional requirements are named but not defined. Baseline lives in `docs/DOMAIN.md`.
- "Changes reflect immediately" is vague. The API is the source of truth; the Vue client refetches after mutations.
- Attendance status needs text or an icon, not color alone.
- Payroll needs periods, components, calculation rules, finalization, and an audit trail.
- The document does not say one company or many. The schema keeps an organization boundary.

## Page inventory

| Route | Who | Job of the page | Required states |
|---|---|---|---|
| `/sign-in` | Everyone | Authenticate with work email and password | default, bad credentials, locked/disabled account, forgot-password entry |
| `/activate-account` | Invited users | Match an invite to employee ID and email, set password, verify email | invite valid, expired, already used, verification sent, verified |
| `/dashboard` | Employee | Today's attendance action, leave balances, next pay date, alerts, recent activity | not checked in, checked in, checked out, on leave, incomplete profile |
| `/dashboard` | HR | Headcount, today's coverage, pending approvals, attendance exceptions | empty queue, partial data, payroll period due |
| `/employees` | HR | Find, filter, add, activate, or open employees | loading, empty, no results, inactive employees |
| `/employees/:employeeId` | Self or HR | Read and edit permitted profile fields through Personal, Job, Salary, and Documents tabs | view, edit, unsaved changes, missing document, access denied |
| `/attendance` | Employee | Check in/out and inspect calendar or weekly timesheet | present, late, missing check-out, leave, half-day, correction requested |
| `/attendance` | HR | Review all attendance and resolve exceptions | filtered list, missing check-out, correction pending, approved correction |
| `/time-off` | Employee | Read balances, view requests, submit or cancel a request | draft, overlap, insufficient balance, pending, approved, rejected |
| `/time-off` | HR | Review requests with balance and overlap context | pending queue, approve, reject with comment, conflict warning |
| `/payroll` | Employee | Read pay-period summary and download payslip | current period, prior period, no published payslip |
| `/payroll` | HR | Edit salary inputs, review exceptions, finalize and publish a period | draft, validation errors, finalized, published, correction needed |
| `/settings` | HR | Configure leave types, workweek, attendance thresholds, payroll components, and company details | valid policy, unsaved changes, destructive-policy warning |

## Navigation and permissions

One application shell with five product areas: Overview, People, Attendance, Time off, and Payroll.

- Employees see Overview, Attendance, Time off, Payroll, and their own profile.
- HR sees all product areas plus the People directory, approvals, editing, and Settings.
- The server enforces every permission.
- MVP uses one `HR` role. If Admin and HR Officer later differ, split the role then.

## Primary flows

### Employee activation

1. HR creates or imports an employee.
2. Dayflow issues a single-use invite tied to organization, employee record, work email, and role.
3. The employee enters employee ID and email, then sets a password.
4. Dayflow verifies the email and activates the account.
5. The employee lands on the personal dashboard.

### Daily attendance

1. The dashboard shows the current attendance state.
2. Check-in creates an open attendance session with server time.
3. Check-out closes that session.
4. A nightly rule derives Present, Absent, Half-day, or Leave from approved leave and worked minutes.
5. The employee requests a correction for mistakes. HR approves or rejects it.

### Leave request

1. The employee selects a leave type and dates.
2. Dayflow shows weekends, holidays, overlap, counted days, and the balance after approval.
3. The employee adds a reason and submits.
4. HR sees the request with balance and overlap context.
5. Approve or reject records the actor, time, and comment.
6. Approval updates leave balance and attendance expectations in one transaction.

### Payroll

1. HR opens a payroll period.
2. Dayflow snapshots salary components and attendance inputs.
3. Validation flags missing salary data, attendance exceptions, or negative net pay.
4. HR finalizes the period. Finalization locks inputs.
5. HR publishes payslips. Employees see only their own published records.

## Visual direction

Follow `docs/UI.md`. Odoo 19 product UI: 46px plum bar, white control panel, `#F8F9FA` canvas, white sheets, 14px system type, shadcn-vue. No decorative cards. No emoji. Status always includes text. Salary stays in Payroll or the Salary tab. The dashboard leads with today's action, not a grid of module shortcuts.

## MVP delivery order

### Build first

1. Organization seed, users, memberships, employees, and invite activation.
2. Shared shell and role-aware dashboard.
3. Employee directory and profile permissions.
4. Attendance session and employee/HR views.
5. Leave balances, requests, and approval flow.
6. Read-only employee payroll and basic HR payroll period management.
7. Audit events and focused authorization tests.

### Cut if time runs out

- Custom settings UI. Seed policies instead.
- Document upload. Show the tab with a deferred state.
- Payroll calculations. Seed a finalized period; keep HR editing limited to salary components.
- Reports and analytics.
- Email notifications other than activation and password reset.

Do not cut server-side authorization, organization isolation, invite-bound roles, or audit records for salary and approvals.

## Definition of done for the prototype

- Employee and HR accounts land on different dashboards.
- An employee cannot open another employee's private data by changing a URL.
- Check-in and check-out create a coherent attendance record.
- An employee can submit a valid leave request and see its status.
- HR can approve or reject the request with an audit record.
- Leave approval changes the employee's leave balance and attendance expectation.
- Employees see only their own published payroll record.
- HR can view all payroll records and update salary inputs before finalization.
- Loading, empty, validation, permission, and error states exist on every core page.
- Keyboard focus, labels, and non-color status indicators are present.

## Next product questions

1. Single-company hackathon build or reusable multi-company product?
2. Who creates the first HR account?
3. Is attendance tied to office location, remote work, shifts, or only server time?
4. Can employees request corrections to attendance?
5. How are weekends, holidays, half-days, and sandwich leave calculated?
6. Does leave require one approver or a manager plus HR?
7. Is payroll a real calculation engine or a read-only salary and payslip demo?
8. Which documents are mandatory, and who can read each type?
9. Must salary data be hidden from some HR officers?
10. What retention and deletion rules apply to employee records?

Hackathon defaults for these questions are in `docs/DOMAIN.md`.
