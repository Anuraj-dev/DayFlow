# Dayflow — Human Resource Management System

**Hackathon problem guide** (from the problem PDF + Excalidraw wireframes)

- Tagline: *Every workday, perfectly aligned.*
- Board title: **Human Resource Management System — 8 hours**
- Organizer workspace: **odoo-rd** (Odoo India R&D style)
- Sources:
  - Problem PDF: `Dayflow - Human Resource Management System.pdf`
  - Wireframes: [Excalidraw board](https://link.excalidraw.com/l/65VNwvy7c4X/58RLEJ4oOwh)

This is an **8-hour** build. The PDF is a requirements outline. The Excalidraw board is the real product spec: screens, copy, business rules, and edge cases. **When they conflict, follow the wireframes.**

---

## 1. What you are building

A small HRMS that digitizes day-to-day HR for two roles:

| Role | What they do |
|------|----------------|
| **Admin / HR Officer** | Create employees, edit everything, see all attendance, approve/reject time off, define salary structure |
| **Employee** | Log in, see the directory, check in/out, view own attendance, request time off, view own profile and salary (read-only) |

Core loops to prove in the demo:

1. HR creates an employee → system assigns Login ID + temporary password.
2. Employee logs in → lands on the employee directory → checks in.
3. Employee requests leave → HR approves/rejects.
4. HR opens Salary Info and wage splits into components automatically.
5. Attendance (and unpaid/missing days) feeds **payable days** for payroll.

---

## 2. What is in vs out of scope

### Must ship (the actual problem)

- Authentication: sign in, first-time password change
- Role-based access (Admin/HR vs Employee)
- Employee directory (card grid) with live status
- Employee profile: view + restricted edit
- Attendance: check-in / check-out, daily/weekly (or month) views
- Time off: apply, balances, approve/reject
- Payroll visibility: employee read-only; admin can set wage + components

### Future / do not spend hackathon time unless you finish early

- Email / notification alerts
- Analytics dashboard, salary slips as generated PDFs, attendance reports
- Real email verification (PDF asks for it; for 8 hours, skip or fake it)

---

## 3. Roles and access matrix

| Capability | Employee | Admin / HR |
|------------|----------|------------|
| Self sign-up | **No** (wireframes) | Yes — HR creates people |
| Sign in | Own account | Own account |
| Employee directory | Yes (cards clickable, **view-only**) | Yes + **NEW** employee |
| Open another employee | View-only | Edit all fields |
| Edit own address / phone / photo | Yes | Yes |
| Salary Info tab | Hidden or read-only | Visible, editable |
| Check in / check out | Own | Own (and see everyone) |
| Attendance list | **Own records**, current month | **All employees**, current day |
| Time off balances / requests | Own only | All + Approve / Reject |
| Payroll / wage update | Read-only | Edit salary structure |

---

## 4. Screens you have to build

The wireframes are an Odoo-like shell: top bar with **Company logo | Employees | Attendance | Time Off**, plus an avatar systray.

### 4.1 Sign in

- Fields: Login ID / Email, Password
- Button: **SIGN IN**
- Link: “Don’t have an account? Sign Up” (this is really the **HR/company signup** path, not employee self-serve)
- Errors on bad credentials
- Success → **Employees** page (not a generic dashboard)

### 4.2 Sign up (company / HR only)

- Company logo upload
- Company name, name, email, phone, password, confirm password
- Employees **cannot** register themselves

### 4.3 Employees directory (home after login)

Both roles land here.

- Search
- **NEW** (Admin/HR only) — create employee
- Grid of employee cards
- Each card: profile picture + basic info
- Status badge, top-right of the card:
  - Green dot — present (checked in)
  - Airplane — on approved leave
  - Yellow dot — absent (no check-in and no approved time off)
- Click card → employee form in **view-only** mode
- Avatar (top right) dropdown: **My Profile**, **Log Out**
- Check In / Check Out control in the systray
  - Before check-in: red status
  - After successful check-in: **red → green**
  - Show “Since hh:mm”

### 4.4 Employee form (Odoo-style notebook)

Header: photo, name, login ID, email, mobile, job, company, department, manager, location.

Tabs:

| Tab | Who sees it | Contents |
|-----|-------------|----------|
| **Resume** | Everyone | About, “What I love about my job”, interests/hobbies, skills (+ Add), certifications |
| **Private Info** | Everyone (employees edit a subset) | DOB, residing address, nationality, personal email, gender, marital status, date of joining, bank details (account, bank name, IFSC), PAN, UAN, emp code |
| **Salary Info** | **Admin/HR only** | See §6 |
| **Security** | Employee “My Profile” | Password change (implied) |

Admin can edit all fields. Employee can edit limited fields: address, phone, profile picture (PDF). Keep job, salary, IDs locked for employees.

### 4.5 Attendance

Shared columns: Date (or employee), Check In, Check Out, Work Hours, Extra Hours.

**Employee view**

- Own day-wise records for the **current month**
- Date navigator (month)
- Summary chips: days present, leaves count, total working days
- Rows keyed by **date**

**Admin / HR view**

- All employees present on the **current day**
- Date navigator (day)
- Rows keyed by **employee**
- Search

Attendance drives payroll: unpaid leave + missing days **reduce payable days**.

### 4.6 Time Off

Top cards (example balances from the board):

- **Paid time off** — 24 days available
- **Sick time off** — 7 days available
- (Unpaid is a request type, typically no balance)

**Employee:** own records only, **NEW** request.

**Admin/HR:** all employees, **Allocation**, **Approve / Reject** (with comments).

List columns: Name, Start Date, End Date, Time off Type, Status (`Pending` / `Approved` / `Rejected`).

**Request modal**

- Employee (prefilled for self)
- Time off type: Paid Time Off | Sick Leave | Unpaid Leaves
- Validity period (from → to)
- Allocation (days)
- Attachment (required conceptually for sick leave certificate)
- Submit / Discard

---

## 5. Login ID and onboarding rules

This is a judging detail. Do not skip it.

When Admin/HR creates an employee, generate:

```
OI + first two of first name + first two of last name + year of joining + 4-digit serial that year
```

Example: employee **Jo Do**, joined **2022**, first joiner that year:

```
OIJODO20220001
```

| Piece | Meaning |
|-------|---------|
| `OI` | Odoo India (company prefix — keep configurable if you have time) |
| `JODO` | First two letters of first name + last name |
| `2022` | Year of joining |
| `0001` | Serial of joiners that year |

Also:

- First password is **auto-generated**
- Employee must be able to log in and **change** it
- Normal users cannot self-register

PDF §3.1.1 says anyone can sign up and pick a role. **Ignore that.** The board is explicit: HR creates users.

---

## 6. Salary / payroll rules

Wage type: **Fixed wage**.

On Salary Info (admin):

- Month wage (example ₹50,000) and yearly wage (₹6,00,000)
- Working schedule: month / yearly, working days per week, break time, hours
- Salary components (auto-calc from wage)
- Statutory: **PF 12% of Basic** (employee + employer), **Professional Tax ₹200**

### Components (from the board)

| Component | How it is computed (example wage ₹50,000) | Example amount |
|-----------|-------------------------------------------|----------------|
| Basic Salary | 50% of **wage** | ₹25,000.00 |
| House Rent Allowance | 50% of **Basic** | ₹12,500.00 |
| Standard Allowance | 16.67% of Basic **or** fixed ₹4,167 | ₹4,167.00 |
| Performance Bonus | 8.33% of Basic | ₹2,082.50 |
| Leave Travel Allowance | 8.33% of Basic | ₹2,082.50 |
| Fixed Allowance | **Wage − sum of the other components** | remainder |

Rules to implement:

1. Each component has a **computation type**: Fixed Amount **or** Percentage.
2. Changing **Month Wage** recalculates every percentage component.
3. **Sum of components must not exceed wage.**
4. Fixed Allowance is the plug: `wage - (basic + hra + standard + bonus + lta)`.
5. PF: `12% × Basic` for employee and again for employer (example ₹3,000 + ₹3,000).
6. Professional Tax: flat ₹200, deducted from gross.
7. Employees see this **read-only**.

Payslip logic (even if you do not generate a PDF):

```
payable_days = working_days_in_period
             - unpaid_leave_days
             - missing_attendance_days
```

Gross for the period is prorated on `payable_days`. That is the link between Attendance, Time Off, and Payroll.

---

## 7. Suggested data model

Keep it small.

- **users** — id, login_id, email, password_hash, role (`admin` \| `employee`), must_change_password
- **employees** — user_id, employee_id/login_id, name, photo, phone, address, job, department, manager_id, location, company, date_of_joining, private/bank fields
- **attendance** — employee_id, date, check_in, check_out, work_hours, extra_hours, status (`present` \| `absent` \| `half_day` \| `leave`)
- **leave_types** — name, paid?, default_allocation (24 / 7 / 0)
- **leave_balances** — employee_id, type_id, days_available
- **leave_requests** — employee_id, type_id, start, end, days, remarks, attachment, status, reviewer_comment
- **salary_structures** — employee_id, month_wage, yearly_wage, schedule fields, pf_rate, professional_tax
- **salary_components** — structure_id, name, compute_type (`percent` \| `fixed`), base (`wage` \| `basic`), rate_or_amount, computed_amount

---

## 8. Conflicts and how to resolve them

| PDF | Excalidraw (use this) |
|-----|------------------------|
| Anyone signs up with role Employee/HR | Employees **cannot** register; HR creates them |
| Email verification required | Skip for 8 hours unless trivial |
| Generic “dashboard” with cards | Land on **Employees** directory |
| Daily/weekly attendance | Employee: **month**, own rows. Admin: **today**, all people |
| Payroll “accuracy” vaguely | Concrete wage split + payable days |
| Sections 4–5 missing (jumps to 6. Future) | Non-functional reqs are unspecified — pick boring defaults |

Password “must follow security rules”: minimum length + mix is enough. Document it.

---

## 9. Eight-hour build order

Treat this as a cut list. Later items are demo polish.

| Hours | Build | Demo value |
|------:|-------|------------|
| 0:00–0:30 | Auth, roles, seed Admin + 2 employees, Login ID generator | Login as both roles |
| 0:30–1:30 | Shell + Employees grid + status dots + click to view-only form | Looks like the board |
| 1:30–2:30 | Create/edit employee (admin), My Profile, avatar menu, photo | HR onboarding story |
| 2:30–4:00 | Check in/out + attendance lists (own vs all) | Green dot live |
| 4:00–5:30 | Time off balances, request modal, approve/reject | The approval loop |
| 5:30–7:00 | Salary Info calc + employee read-only payroll | The “wow” formula |
| 7:00–8:00 | Payable-days hook, seed realistic data, demo path, README | Survive judging |

If you slip, **cut** Resume fluff, bank fields, extra hours, and sick-leave attachments. Do **not** cut: roles, Login ID, check-in, leave approval, wage split.

---

## 10. Demo script (5 minutes)

1. Sign in as **HR**. Show Employees grid with mixed status (present / leave / absent).
2. Click **NEW**. Create “Jo Do”. Show generated id `OIJODO2026xxxx` and temp password.
3. Open that employee → **Salary Info**. Set wage ₹50,000. Show Basic 25k, HRA 12.5k, remainder as Fixed Allowance.
4. Log out. Sign in as the new employee (forced password change optional). Land on directory. **Check In**. Dot turns green.
5. **Time Off → NEW** sick/paid request. Switch to HR. Approve. Employee card shows airplane.
6. Open Attendance: employee sees own month; HR sees everyone’s day.
7. Mention: missing attendance and unpaid leave reduce payable days.

---

## 11. Acceptance checklist

Copy this into your issue tracker or README.

**Auth**

- [ ] Sign in with email or login ID
- [ ] Bad password shows an error
- [ ] Employee cannot self-register
- [ ] HR create-user generates Login ID in `OI + 2+2 + year + serial` form
- [ ] First password is system-generated and can be changed

**Directory & profile**

- [ ] Post-login page is Employees, not an empty dashboard
- [ ] Cards show photo + status (green / airplane / yellow)
- [ ] Card click is view-only
- [ ] Admin can edit all employee fields; employee can edit address/phone/photo
- [ ] Salary Info tab is admin-only
- [ ] Avatar menu: My Profile, Log Out

**Attendance**

- [ ] Check in / check out from the shell
- [ ] Check-in flips status to present (green)
- [ ] Employee sees only own rows (month)
- [ ] Admin sees all employees (day)
- [ ] Statuses: Present, Absent, Half-day, Leave

**Time off**

- [ ] Types: Paid, Sick, Unpaid
- [ ] Request: type, date range, remarks, status Pending
- [ ] Admin approve/reject + comment; employee record updates immediately
- [ ] Employee cannot see others’ requests

**Payroll**

- [ ] Wage change recalculates components
- [ ] Components cannot exceed wage
- [ ] Employee payroll is read-only
- [ ] Payable days consider unpaid leave and missing attendance

**UX**

- [ ] Shared nav: Employees, Attendance, Time Off
- [ ] Two roles feel different without extra apps
- [ ] Seed data is enough to demo without typing for 3 minutes

---

## 12. Implementation notes (practical)

The board copies **Odoo HR** (Employees, Attendance, Time Off, work entries, salary structure). You can:

- Build a **custom web app** that *looks* like those screens, or
- Customize **Odoo** `hr`, `hr_attendance`, `hr_holidays`, and payroll-style fields

Either is valid if the flows above work. For 8 hours, a focused web app with a clean Odoo-like layout is usually faster than a full Odoo module unless the team already lives in Odoo.

Suggested defaults if the PDF is silent:

- Stack: whatever the team already knows
- Currency: INR
- Company prefix: `OI` (make it a constant)
- Working day: 10:00–19:00, 9h work, extra hours if checkout is later (as in the sample rows)
- Time off year: simple annual balances, no accrual engine

---

## 13. One-page summary

**Problem:** Replace spreadsheet HR with a two-role app for directory, attendance, leave, and salary.

**Solve:** HR-created employees with structured Login IDs, live presence, check-in, leave approval, and automatic salary breakdown tied to attendance.

**Do not solve:** notifications, analytics, email verification, a full statutory Indian payroll engine.

**Win the room:** Login ID format + live status dots + wage auto-split + approve-leave-in-front-of-judges.
