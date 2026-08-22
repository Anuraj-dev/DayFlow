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
}

export interface PayrollRecord {
  id: string
  employee_id?: string
  net_amount: string
  currency: string
  published_at: string | null
}

export interface PayrollHome {
  role: string
  periods: PayrollPeriod[]
  records: PayrollRecord[]
}
