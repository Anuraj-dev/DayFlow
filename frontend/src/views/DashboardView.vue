<script setup lang="ts">
import {
  BanIcon,
  BriefcaseBusinessIcon,
  CalendarDaysIcon,
  CircleCheckIcon,
  Clock3Icon,
  HeartPulseIcon,
} from '@lucide/vue'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { api, HttpError } from '@/api/client'
import { attendanceStatusLabel, statusTone } from '@/lib/status'
import { useAttendanceStore } from '@/stores/attendance'
import { useSessionStore } from '@/stores/session'
import type { DashboardPayload, LeaveBalance } from '@/types/domain'

const session = useSessionStore()
const attendance = useAttendanceStore()
const router = useRouter()
const loading = ref(true)
const error = ref('')
const payload = ref<DashboardPayload | null>(null)
const actionError = ref('')
const actionStatus = ref('')
const controlActionsReady = ref(false)

const employee = computed(() => (payload.value?.kind === 'EMPLOYEE' ? payload.value : null))
const hr = computed(() => (payload.value?.kind === 'HR' ? payload.value : null))
const balances = computed<LeaveBalance[]>(() => employee.value?.leave_balances ?? [])
const attendanceLabel = computed(() => attendanceStatusLabel(employee.value?.attendance_state))
const attendanceTone = computed(() => statusTone(attendanceLabel.value))
const canCheckIn = computed(
  () =>
    attendance.canCheckIn &&
    employee.value?.attendance_state !== 'on_leave' &&
    employee.value?.attendance_state !== 'checked_out',
)
const canCheckOut = computed(() => attendance.canCheckOut)
const coverageLabel = computed(
  () => hr.value?.today_coverage || hr.value?.headline || 'Not reported',
)
const queueEmpty = computed(
  () =>
    Boolean(hr.value) && hr.value!.pending_approvals === 0 && hr.value!.attendance_exceptions === 0,
)
const profilePath = computed(() =>
  session.user?.employee_id ? `/employees/${session.user.employee_id}` : '/dashboard',
)

onMounted(async () => {
  await nextTick()
  controlActionsReady.value = Boolean(document.getElementById('control-actions'))
  try {
    payload.value = await api('/api/dashboard')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load dashboard.'
  } finally {
    loading.value = false
  }
})

async function punch(path: '/api/attendance/check-in' | '/api/attendance/check-out') {
  actionError.value = ''
  actionStatus.value = ''
  try {
    await attendance.punch(path)
    payload.value = await api('/api/dashboard')
    actionStatus.value = path.endsWith('check-in')
      ? 'Checked in successfully.'
      : 'Checked out successfully.'
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Attendance action failed.'
  }
}

watch(
  () => attendance.revision,
  async (value, previous) => {
    if (!value || !previous || !payload.value || payload.value.kind !== 'EMPLOYEE') return
    try {
      payload.value = await api('/api/dashboard')
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Could not load dashboard.'
    }
  },
)

async function openPayroll() {
  await router.push({ name: 'payroll' })
}

function leaveIcon(leaveType: string) {
  switch (leaveType.toLowerCase()) {
    case 'paid':
      return CalendarDaysIcon
    case 'sick':
      return HeartPulseIcon
    case 'unpaid':
      return BanIcon
    default:
      return BriefcaseBusinessIcon
  }
}

function formatDashboardDate(value: string) {
  return new Intl.DateTimeFormat('en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`))
}

function dashboardLeaveLabel(leaveType: string) {
  const normalized = leaveType.trim().toLowerCase()
  if (normalized === 'paid') return 'Paid'
  if (normalized === 'sick') return 'Sick'
  if (normalized === 'unpaid') return 'Unpaid'
  return leaveType.replace(/_/g, ' ')
}
</script>

<template>
  <section class="sheet dashboard-sheet">
    <Teleport v-if="controlActionsReady" defer to="#control-actions">
      <div class="flex items-center gap-2">
        <template v-if="employee">
          <Button type="button" :disabled="!canCheckIn" @click="punch('/api/attendance/check-in')">
            Check in
          </Button>
          <Button
            type="button"
            variant="outline"
            :disabled="!canCheckOut"
            @click="punch('/api/attendance/check-out')"
          >
            Check out
          </Button>
        </template>
        <Button v-else-if="hr?.payroll_period_due" type="button" @click="openPayroll"
          >Open payroll</Button
        >
      </div>
    </Teleport>

    <PageHeader
      :title="session.isHr ? 'HR overview' : 'Today'"
      :description="
        session.isHr
          ? 'Review coverage and exceptions, not every row.'
          : 'Start with today’s attendance action.'
      "
    />
    <p v-if="loading">Loading dashboard…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>

    <div v-else-if="employee" class="employee-dashboard">
      <Alert v-if="employee.incomplete_profile">
        <AlertTitle>Incomplete profile</AlertTitle>
        <AlertDescription>
          Add missing personal details on
          <RouterLink class="text-[#017E84] underline" :to="profilePath">My profile</RouterLink>
          before the next payroll cut-off.
        </AlertDescription>
      </Alert>

      <div class="dashboard-columns">
        <section class="attendance-summary" aria-labelledby="attendance-heading">
          <div class="section-heading attendance-heading-row">
            <div class="section-title">
              <Clock3Icon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
              <h2 id="attendance-heading">Attendance</h2>
            </div>
            <div class="attendance-status" :data-tone="attendanceTone" role="status">
              <CircleCheckIcon
                v-if="attendanceTone === 'confirmed'"
                class="size-5"
                :stroke-width="2.25"
                aria-hidden="true"
              />
              <Clock3Icon v-else class="size-5" :stroke-width="2" aria-hidden="true" />
              <span>{{ attendanceLabel }}</span>
            </div>
          </div>

          <p class="attendance-headline">{{ employee.headline }}</p>

          <dl class="attendance-details">
            <div>
              <dt>Next pay date</dt>
              <dd>
                {{
                  employee.next_pay_date
                    ? formatDashboardDate(employee.next_pay_date)
                    : 'Not scheduled'
                }}
              </dd>
            </div>
          </dl>

          <RouterLink class="dashboard-link" to="/attendance">View attendance</RouterLink>

          <div v-if="!controlActionsReady" class="mt-4 flex gap-2">
            <Button
              type="button"
              :disabled="!canCheckIn"
              @click="punch('/api/attendance/check-in')"
            >
              Check in
            </Button>
            <Button
              type="button"
              variant="outline"
              :disabled="!canCheckOut"
              @click="punch('/api/attendance/check-out')"
            >
              Check out
            </Button>
          </div>
        </section>

        <section class="leave-summary" aria-labelledby="leave-heading">
          <div class="section-heading">
            <div class="section-title">
              <BriefcaseBusinessIcon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
              <h2 id="leave-heading">Leave balances</h2>
            </div>
            <RouterLink class="dashboard-link" to="/time-off">Request time off</RouterLink>
          </div>

          <div v-if="balances.length" class="hidden sm:block">
            <Table>
              <TableCaption class="sr-only">Leave balances</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead class="text-right">Remaining days</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="row in balances" :key="row.leave_type">
                  <TableCell>
                    <span class="leave-type">
                      <component
                        :is="leaveIcon(row.leave_type)"
                        class="size-5 shrink-0"
                        :stroke-width="1.75"
                        aria-hidden="true"
                      />
                      {{ dashboardLeaveLabel(row.leave_type) }} leave
                    </span>
                  </TableCell>
                  <TableCell class="text-right tabular-nums"
                    >{{ row.remaining_days }} days</TableCell
                  >
                </TableRow>
              </TableBody>
            </Table>
          </div>

          <div v-if="balances.length" class="mobile-record-list">
            <div
              v-for="row in balances"
              :key="row.leave_type"
              class="mobile-record mobile-record-row"
            >
              <span class="leave-type">
                <component
                  :is="leaveIcon(row.leave_type)"
                  class="size-5 shrink-0"
                  :stroke-width="1.75"
                  aria-hidden="true"
                />
                {{ dashboardLeaveLabel(row.leave_type) }} leave
              </span>
              <strong class="tabular-nums">{{ row.remaining_days }} days</strong>
            </div>
          </div>

          <EmptyState
            v-else
            title="Balances"
            body="Paid, sick, and unpaid balances load from the leave service."
          />
        </section>
      </div>

      <div class="current-attendance">
        <div class="current-attendance-status" :data-tone="attendanceTone">
          <CircleCheckIcon
            v-if="attendanceTone === 'confirmed'"
            class="size-5"
            :stroke-width="2.25"
            aria-hidden="true"
          />
          <Clock3Icon v-else class="size-5" :stroke-width="2" aria-hidden="true" />
          <strong>{{ attendanceLabel }}</strong>
        </div>
        <span class="current-attendance-detail">{{ employee.headline }}</span>
        <RouterLink class="dashboard-link current-attendance-link" to="/attendance"
          >View week</RouterLink
        >
      </div>

      <div class="dashboard-feedback" aria-live="polite">
        <p v-if="actionError" class="feedback-error" role="alert">{{ actionError }}</p>
        <p v-if="actionStatus" class="feedback-success" role="status">{{ actionStatus }}</p>
      </div>
    </div>

    <div v-else-if="hr" class="grid gap-4">
      <h2 class="mt-0">{{ hr.headline }}</h2>
      <p v-if="queueEmpty" class="text-[#495057]">
        Queue empty. No leave approvals or attendance exceptions today.
      </p>
      <Table>
        <TableCaption class="sr-only">HR coverage</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Metric</TableHead>
            <TableHead>Value</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>
              <RouterLink class="text-[#017E84] underline" to="/employees">Headcount</RouterLink>
            </TableCell>
            <TableCell>{{ hr.headcount }}</TableCell>
            <TableCell>
              <StatusBadge
                :label="hr.headcount ? 'Staffed' : 'Empty'"
                :tone="hr.headcount ? 'confirmed' : 'review'"
              />
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Coverage</TableCell>
            <TableCell>{{ coverageLabel }}</TableCell>
            <TableCell>
              <StatusBadge label="Reported" tone="confirmed" />
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell>
              <RouterLink class="text-[#017E84] underline" to="/time-off"
                >Pending approvals</RouterLink
              >
            </TableCell>
            <TableCell>{{ hr.pending_approvals }}</TableCell>
            <TableCell>
              <StatusBadge
                :label="hr.pending_approvals ? 'Pending' : 'Queue empty'"
                :tone="hr.pending_approvals ? 'review' : 'confirmed'"
              />
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell>
              <RouterLink class="text-[#017E84] underline" to="/attendance"
                >Attendance exceptions</RouterLink
              >
            </TableCell>
            <TableCell>{{ hr.attendance_exceptions }}</TableCell>
            <TableCell>
              <StatusBadge
                :label="hr.attendance_exceptions ? 'Needs review' : 'Clear'"
                :tone="hr.attendance_exceptions ? 'review' : 'confirmed'"
              />
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell>
              <RouterLink class="text-[#017E84] underline" to="/payroll"
                >Payroll period due</RouterLink
              >
            </TableCell>
            <TableCell>{{ hr.payroll_period_due ? 'Yes' : 'No' }}</TableCell>
            <TableCell>
              <StatusBadge
                :label="hr.payroll_period_due ? 'Due' : 'On track'"
                :tone="hr.payroll_period_due ? 'review' : 'confirmed'"
              />
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  </section>
</template>

<style scoped>
.dashboard-sheet {
  margin-inline: auto;
  max-width: 1400px;
}

.employee-dashboard {
  display: grid;
  gap: 1.5rem;
}

.dashboard-columns {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(420px, 1.6fr);
  gap: 0;
  margin-top: 0.5rem;
}

.attendance-summary,
.leave-summary {
  min-width: 0;
}

.attendance-summary {
  padding-right: 48px;
}

.leave-summary {
  border-left: 1px solid var(--line);
  padding-left: 48px;
}

.section-heading,
.section-title,
.attendance-status,
.leave-type {
  display: flex;
  align-items: center;
}

.section-heading {
  min-height: 32px;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.attendance-heading-row {
  align-items: flex-start;
  flex-wrap: wrap;
}

.section-title {
  gap: 12px;
}

.section-title h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
}

.section-icon {
  width: 22px;
  height: 22px;
  flex: none;
  color: var(--muted-text);
}

.attendance-status {
  gap: 7px;
  min-height: 28px;
  color: var(--muted-text);
  font-weight: 700;
}

.attendance-status[data-tone='confirmed'] {
  color: #168234;
}

.attendance-status[data-tone='review'] {
  color: #8a5b00;
}

.attendance-status[data-tone='danger'] {
  color: var(--danger);
}

.attendance-headline {
  margin: 0 0 28px;
  color: var(--muted-text);
  font-size: 16px;
}

.attendance-details {
  margin: 0 0 24px;
  border-top: 1px solid var(--line);
  padding-top: 18px;
}

.attendance-details > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.attendance-details dt,
.attendance-details dd {
  margin: 0;
}

.attendance-details dt {
  color: var(--muted-text);
}

.attendance-details dd {
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.dashboard-link {
  color: var(--action);
  font-weight: 500;
  text-decoration: none;
  text-underline-offset: 3px;
}

.dashboard-link:hover {
  text-decoration: underline;
}

.leave-type {
  gap: 12px;
}

.dashboard-feedback:empty {
  display: none;
}

.mobile-record-list {
  display: grid;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--sheet);
}

.mobile-record {
  display: grid;
  gap: 10px;
  padding: 16px;
}

.mobile-record + .mobile-record {
  border-top: 1px solid var(--line);
}

.mobile-record-row {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.current-attendance,
.current-attendance-status {
  display: flex;
  align-items: center;
}

.current-attendance {
  gap: 28px;
  border-top: 1px solid var(--line);
  padding-top: 20px;
}

.current-attendance-status {
  gap: 8px;
  color: var(--muted-text);
}

.current-attendance-status[data-tone='confirmed'] {
  color: #168234;
}

.current-attendance-status[data-tone='review'] {
  color: #8a5b00;
}

.current-attendance-status[data-tone='danger'] {
  color: var(--danger);
}

.current-attendance-detail {
  color: var(--muted-text);
}

.current-attendance-link {
  margin-left: auto;
}

.dashboard-feedback .feedback-success,
.dashboard-feedback .feedback-error {
  margin: 0;
  border: 1px solid;
  border-radius: 4px;
  padding: 9px 11px;
}

.dashboard-feedback .feedback-success {
  border-color: #7fbe8f;
  background: var(--success-bg);
  color: #146c2e;
}

.dashboard-feedback .feedback-error {
  border-color: #e3a0a9;
  background: var(--danger-bg);
  color: #a61b29;
}

@media (min-width: 640px) {
  .mobile-record-list {
    display: none;
  }
}

@media (max-width: 767px) {
  .dashboard-columns {
    grid-template-columns: minmax(0, 1fr);
    gap: 32px;
    margin-top: 20px;
  }

  .attendance-summary {
    padding-right: 0;
  }

  .leave-summary {
    border-top: 1px solid var(--line);
    border-left: 0;
    padding-top: 28px;
    padding-left: 0;
  }

  .section-heading {
    align-items: flex-start;
    margin-bottom: 18px;
  }

  .current-attendance {
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 8px 20px;
  }

  .current-attendance-detail {
    order: 3;
    width: 100%;
  }
}

@media (max-width: 420px) {
  .attendance-heading-row,
  .leave-summary .section-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
