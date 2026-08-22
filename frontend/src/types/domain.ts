export type Role = 'EMPLOYEE' | 'HR'

export type EmployeeStatus = 'INVITED' | 'ACTIVE' | 'INACTIVE'

export interface SessionUser {
  id: string
  email: string
  role: Role
  organization_id: string
  employee_id: string | null
  first_name: string | null
  last_name: string | null
  employee_code: string | null
}

export interface SignInResponse {
  access_token: string
  token_type: string
  user: SessionUser
}

export interface EmployeeSummary {
  id: string
  employee_code: string
  first_name: string
  last_name: string
  status: EmployeeStatus
  email?: string | null
  role?: Role | null
  phone?: string | null
  address?: string | null
  department?: string | null
  title?: string | null
  employment_type?: string | null
  location?: string | null
  joined_on?: string | null
  presence?: string | null
  date_of_birth?: string | null
  nationality?: string | null
  gender?: string | null
  marital_status?: string | null
  personal_email?: string | null
  bank_account_number?: string | null
  bank_name?: string | null
  ifsc?: string | null
  pan?: string | null
  uan?: string | null
}

export interface ApiError {
  detail: string
}

export interface LeaveBalance {
  leave_type: string
  remaining_days: number
  granted_days?: number
  used_days?: number
}

export interface EmployeeDashboard {
  kind: 'EMPLOYEE'
  headline: string
  attendance_state: string
  leave_balances: LeaveBalance[]
  next_pay_date: string | null
  incomplete_profile: boolean
}

export interface HrDashboard {
  kind: 'HR'
  headline: string
  headcount: number
  pending_approvals: number
  attendance_exceptions: number
  payroll_period_due: boolean
  today_coverage?: string
}

export type DashboardPayload = EmployeeDashboard | HrDashboard

export interface AttendanceSession {
  id: string
  employee_id?: string
  work_date?: string
  check_in_at: string | null
  check_out_at: string | null
  status?: string
  source?: string
  worked_minutes?: number | null
  correction_status?: string | null
}

export interface AttendanceException {
  id: string
  employee_id?: string
  employee_name?: string
  kind: string
  status: string
  work_date?: string | null
  current_check_in_at?: string | null
  current_check_out_at?: string | null
  proposed_check_in_at?: string | null
  proposed_check_out_at?: string | null
  reason?: string | null
}

export interface AttendanceHome {
  role: string
  employee_id: string | null
  sessions: AttendanceSession[]
  open_session: { id: string; check_in_at: string } | null
  exceptions: AttendanceException[]
}

export interface LeaveRequest {
  id: string
  leave_type: string
  starts_on: string
  ends_on: string
  status: string
  employee_id?: string
  employee_name?: string
  counted_days?: number
  reason?: string
  review_comment?: string | null
}

export interface TimeOffHome {
  role: string
  employee_id?: string | null
  balances: LeaveBalance[]
  requests: LeaveRequest[]
  pending_queue: LeaveRequest[]
}

export interface PayrollPeriod {
  id: string
  starts_on: string
  ends_on: string
  pay_date: string
  status: string
  validation_errors?: string[]
  correction_needed?: boolean
}

export interface PayrollRecordLine {
  code: string
  label: string
  amount: string
  kind?: string
}

export interface PayrollRecord {
  id: string
  employee_id?: string
  employee_name?: string
  payroll_period_id?: string
  gross_amount?: string
  deduction_amount?: string
  net_amount: string
  currency: string
  published_at: string | null
  lines?: PayrollRecordLine[]
}

export interface SalaryComponentAmount {
  code: string
  name?: string
  kind?: string
  calculation_type?: string
  rate?: string | null
  amount: string
  editable?: boolean
}

export interface SalaryLine {
  code: string
  name: string
  kind: string
  calculation_type: string
  rate: string | null
  amount: string
  editable: boolean
}

export interface EmployeeSalary {
  employee_id: string
  monthly_wage: string
  currency: string
  effective_from: string
  gross_amount: string
  deduction_amount: string
  net_amount: string
  employer_amount: string
  lines: SalaryLine[]
}

export interface EmployeeSalaryInputs {
  employee_id: string
  employee_name?: string
  monthly_wage?: string
  net_amount?: string
  components: SalaryLine[] | SalaryComponentAmount[]
}

export interface PayrollException {
  kind: string
  detail: string
  employee_id?: string
  employee_name?: string
}

export interface PayrollHome {
  role: string
  periods: PayrollPeriod[]
  records: PayrollRecord[]
  salary_inputs?: EmployeeSalaryInputs[]
  exceptions?: PayrollException[]
}

export interface SalaryComponentPatchResponse {
  employee_id: string
  monthly_wage?: string
  components?: SalaryComponentAmount[]
  lines?: SalaryLine[]
}
