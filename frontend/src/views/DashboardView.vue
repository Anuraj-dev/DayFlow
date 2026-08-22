<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
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
const loading = ref(true)
const error = ref('')
const payload = ref<DashboardPayload | null>(null)
const actionError = ref('')

const employee = computed(() => (payload.value?.kind === 'EMPLOYEE' ? payload.value : null))
const hr = computed(() => (payload.value?.kind === 'HR' ? payload.value : null))
const balances = computed<LeaveBalance[]>(() => employee.value?.leave_balances ?? [])
const attendanceLabel = computed(() => attendanceStatusLabel(employee.value?.attendance_state))

onMounted(async () => {
  try {
    payload.value = await api('/api/dashboard')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load dashboard.'
  } finally {
    loading.value = false
  }
})

async function checkIn() {
  actionError.value = ''
  try {
    await api('/api/attendance/check-in', { method: 'POST' })
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not check in.'
  }
}
</script>

<template>
  <section class="sheet">
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
      <div>
        <h2 class="mt-0">Attendance action</h2>
        <StatusBadge :label="attendanceLabel" :tone="statusTone(attendanceLabel)" />
        <p class="text-[#495057]">{{ employee.headline }}</p>
        <p>Next pay date {{ employee.next_pay_date ?? 'not scheduled' }}</p>
        <p v-if="actionError" role="alert">{{ actionError }}</p>
        <Button type="button" @click="checkIn">Check in</Button>
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
