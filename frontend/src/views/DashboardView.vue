<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
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
import { useSessionStore } from '@/stores/session'
import type { DashboardPayload, LeaveBalance } from '@/types/domain'

const session = useSessionStore()
const router = useRouter()
const loading = ref(true)
const error = ref('')
const payload = ref<DashboardPayload | null>(null)
const actionError = ref('')
const controlActionsReady = ref(false)

const employee = computed(() => (payload.value?.kind === 'EMPLOYEE' ? payload.value : null))
const hr = computed(() => (payload.value?.kind === 'HR' ? payload.value : null))
const balances = computed<LeaveBalance[]>(() => employee.value?.leave_balances ?? [])
const attendanceLabel = computed(() => attendanceStatusLabel(employee.value?.attendance_state))
const canCheckIn = computed(() => employee.value?.attendance_state === 'not_checked_in')
const canCheckOut = computed(() => employee.value?.attendance_state === 'checked_in')
const coverageLabel = computed(() => hr.value?.today_coverage || hr.value?.headline || 'Not reported')
const queueEmpty = computed(
  () => Boolean(hr.value) && hr.value!.pending_approvals === 0 && hr.value!.attendance_exceptions === 0,
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
  try {
    await api(path, { method: 'POST' })
    payload.value = await api('/api/dashboard')
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Attendance action failed.'
  }
}

async function openPayroll() {
  await router.push({ name: 'payroll' })
}
</script>

<template>
  <section class="sheet">
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
        <Button v-else-if="hr?.payroll_period_due" type="button" @click="openPayroll">Open payroll</Button>
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

    <div v-else-if="employee" class="grid gap-6">
      <Alert v-if="employee.incomplete_profile">
        <AlertTitle>Incomplete profile</AlertTitle>
        <AlertDescription>
          Add missing personal details on
          <RouterLink class="underline" :to="profilePath">My profile</RouterLink>
          before the next payroll cut-off.
        </AlertDescription>
      </Alert>

      <div>
        <h2 class="mt-0">Attendance action</h2>
        <StatusBadge :label="attendanceLabel" :tone="statusTone(attendanceLabel)" />
        <p class="text-[#495057]">{{ employee.headline }}</p>
        <p>Next pay date {{ employee.next_pay_date ?? 'not scheduled' }}</p>
        <p v-if="actionError" role="alert">{{ actionError }}</p>
        <div v-if="!controlActionsReady" class="mt-3 flex gap-2">
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
        </div>
      </div>

      <div>
        <h2>Leave balances</h2>
        <Table v-if="balances.length">
          <TableCaption class="sr-only">Leave balances</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Type</TableHead>
              <TableHead>Remaining days</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="row in balances" :key="row.leave_type">
              <TableCell>{{ row.leave_type }}</TableCell>
              <TableCell>{{ row.remaining_days }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <EmptyState v-else title="Balances" body="Paid, sick, and unpaid balances load from the leave service." />
      </div>
    </div>

    <div v-else-if="hr" class="grid gap-4">
      <h2 class="mt-0">{{ hr.headline }}</h2>
      <p v-if="queueEmpty" class="text-[#495057]">Queue empty. No leave approvals or attendance exceptions today.</p>
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
            <TableCell>Headcount</TableCell>
            <TableCell>{{ hr.headcount }}</TableCell>
            <TableCell>
              <StatusBadge :label="hr.headcount ? 'Staffed' : 'Empty'" :tone="hr.headcount ? 'confirmed' : 'review'" />
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
            <TableCell>Pending approvals</TableCell>
            <TableCell>{{ hr.pending_approvals }}</TableCell>
            <TableCell>
              <StatusBadge
                :label="hr.pending_approvals ? 'Pending' : 'Queue empty'"
                :tone="hr.pending_approvals ? 'review' : 'confirmed'"
              />
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Attendance exceptions</TableCell>
            <TableCell>{{ hr.attendance_exceptions }}</TableCell>
            <TableCell>
              <StatusBadge
                :label="hr.attendance_exceptions ? 'Needs review' : 'Clear'"
                :tone="hr.attendance_exceptions ? 'review' : 'confirmed'"
              />
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell>Payroll period due</TableCell>
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
