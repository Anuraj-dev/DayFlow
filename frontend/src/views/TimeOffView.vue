<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import { api, HttpError } from '@/api/client'
import { countedWorkdays, isBlockingLeaveStatus, leaveRequiresBalance, rangesOverlap } from '@/lib/leave'
import { leaveStatusLabel, statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type { LeaveRequest, TimeOffHome } from '@/types/domain'

const LEAVE_TYPES = ['PAID', 'SICK', 'UNPAID'] as const

const session = useSessionStore()
const data = ref<TimeOffHome | null>(null)
const error = ref('')
const actionError = ref('')
const loading = ref(true)
const leaveType = ref<(typeof LEAVE_TYPES)[number]>('PAID')
const startsOn = ref('')
const endsOn = ref('')
const reason = ref('')
const submitting = ref(false)
const reviewComment = ref('')

const draftCounted = computed(() => countedWorkdays(startsOn.value, endsOn.value))

const remainingForType = computed(() => {
  const row = data.value?.balances.find((item) => item.leave_type.toUpperCase() === leaveType.value)
  return row?.remaining_days ?? 0
})

const overlap = computed(() => {
  if (!startsOn.value || !endsOn.value) return false
  return (data.value?.requests ?? []).some(
    (row) =>
      isBlockingLeaveStatus(row.status) &&
      rangesOverlap(startsOn.value, endsOn.value, row.starts_on, row.ends_on),
  )
})

const insufficient = computed(() => {
  if (!startsOn.value || !endsOn.value) return false
  if (!leaveRequiresBalance(leaveType.value)) return false
  return draftCounted.value > remainingForType.value
})

const draftKind = computed<'draft' | 'overlap' | 'insufficient' | null>(() => {
  if (!startsOn.value || !endsOn.value) return null
  if (overlap.value) return 'overlap'
  if (insufficient.value) return 'insufficient'
  return 'draft'
})

const draftLabel = computed(() => {
  if (draftKind.value === 'overlap') return leaveStatusLabel('overlap')
  if (draftKind.value === 'insufficient') return leaveStatusLabel('insufficient')
  if (draftKind.value === 'draft') return leaveStatusLabel('draft')
  return ''
})

const canSubmit = computed(() => {
  return Boolean(
    startsOn.value &&
      endsOn.value &&
      reason.value.trim() &&
      draftCounted.value > 0 &&
      !overlap.value &&
      !insufficient.value &&
      !submitting.value,
  )
})

function requestConflicts(row: LeaveRequest): boolean {
  return (data.value?.requests ?? []).some(
    (other) =>
      other.id !== row.id &&
      (other.employee_id ?? '') === (row.employee_id ?? '') &&
      isBlockingLeaveStatus(other.status) &&
      rangesOverlap(row.starts_on, row.ends_on, other.starts_on, other.ends_on),
  )
}

async function loadHome() {
  data.value = await api<TimeOffHome>('/api/time-off')
}

onMounted(async () => {
  try {
    await loadHome()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load time off.'
  } finally {
    loading.value = false
  }
})

async function submitRequest() {
  actionError.value = ''
  if (overlap.value) {
    actionError.value = 'Leave range overlaps a pending or approved request.'
    return
  }
  if (insufficient.value) {
    actionError.value = 'Insufficient leave balance.'
    return
  }
  if (!reason.value.trim()) {
    actionError.value = 'A reason is required.'
    return
  }
  submitting.value = true
  try {
    await api('/api/time-off/requests', {
      method: 'POST',
      body: JSON.stringify({
        leave_type: leaveType.value,
        starts_on: startsOn.value,
        ends_on: endsOn.value,
        reason: reason.value.trim(),
      }),
    })
    startsOn.value = ''
    endsOn.value = ''
    reason.value = ''
    await loadHome()
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not submit leave.'
  } finally {
    submitting.value = false
  }
}

async function decide(id: string, decision: 'approve' | 'reject') {
  actionError.value = ''
  const comment = reviewComment.value.trim()
  if (decision === 'reject' && !comment) {
    actionError.value = 'Rejection requires a comment.'
    return
  }
  try {
    await api(`/api/time-off/requests/${id}/${decision}`, {
      method: 'POST',
      body: JSON.stringify({ comment: comment || null }),
    })
    reviewComment.value = ''
    await loadHome()
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not update leave.'
  }
}

async function cancelRequest(id: string) {
  actionError.value = ''
  try {
    await api(`/api/time-off/requests/${id}/cancel`, { method: 'POST' })
    await loadHome()
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not cancel leave.'
  }
}
</script>

<template>
  <section class="sheet">
    <PageHeader
      :title="session.isHr ? 'Leave approvals' : 'Time off'"
      :description="
        session.isHr
          ? 'Approve or reject with balance and overlap context.'
          : 'Balances, requests, and a single request form.'
      "
    />
    <p v-if="loading">Loading time off…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <div v-else class="grid gap-6">
      <p v-if="actionError" role="alert">{{ actionError }}</p>

      <div v-if="session.isHr">
        <h2 class="mt-0">Pending queue</h2>
        <label class="mb-3 grid max-w-lg gap-1 text-sm font-medium">
          Review comment
          <Textarea v-model="reviewComment" rows="3" />
        </label>
        <EmptyState
          v-if="!data?.pending_queue.length"
          title="No pending requests"
          body="Rejection requires a comment. Approval updates balance and attendance in one transaction."
        />
        <Table v-else>
          <TableCaption class="sr-only">Pending leave requests</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Employee</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Dates</TableHead>
              <TableHead>Counted days</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Context</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="row in data?.pending_queue ?? []" :key="row.id">
              <TableCell>{{ row.employee_name ?? 'Employee' }}</TableCell>
              <TableCell>{{ row.leave_type }}</TableCell>
              <TableCell>{{ row.starts_on }} – {{ row.ends_on }}</TableCell>
              <TableCell>{{ row.counted_days ?? '—' }}</TableCell>
              <TableCell>
                <StatusBadge :label="leaveStatusLabel(row.status)" :tone="statusTone(leaveStatusLabel(row.status))" />
              </TableCell>
              <TableCell>
                <p v-if="requestConflicts(row)" class="m-0">
                  Conflict: overlaps another pending or approved request.
                </p>
                <p v-else class="m-0 text-[#495057]">No overlap</p>
              </TableCell>
              <TableCell class="flex gap-2">
                <Button type="button" size="sm" @click="decide(row.id, 'approve')">Approve</Button>
                <Button type="button" size="sm" variant="outline" @click="decide(row.id, 'reject')">Reject</Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>

      <template v-else>
        <Table>
          <TableCaption class="sr-only">Leave balances</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Type</TableHead>
              <TableHead>Remaining days</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="!data?.balances.length">
              <TableCell colspan="2">No balances yet</TableCell>
            </TableRow>
            <TableRow v-for="row in data?.balances ?? []" :key="row.leave_type">
              <TableCell>{{ row.leave_type }}</TableCell>
              <TableCell>{{ row.remaining_days }}</TableCell>
            </TableRow>
          </TableBody>
        </Table>

        <div>
          <h2>Requests</h2>
          <Table>
            <TableCaption class="sr-only">Leave requests</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Type</TableHead>
                <TableHead>Dates</TableHead>
                <TableHead>Counted days</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="!data?.requests.length">
                <TableCell colspan="5">No requests yet</TableCell>
              </TableRow>
              <TableRow v-for="row in data?.requests ?? []" :key="row.id">
                <TableCell>{{ row.leave_type }}</TableCell>
                <TableCell>{{ row.starts_on }} – {{ row.ends_on }}</TableCell>
                <TableCell>{{ row.counted_days ?? '—' }}</TableCell>
                <TableCell>
                  <StatusBadge :label="leaveStatusLabel(row.status)" :tone="statusTone(leaveStatusLabel(row.status))" />
                </TableCell>
                <TableCell>
                  <Button
                    v-if="row.status.toUpperCase() === 'PENDING'"
                    type="button"
                    size="sm"
                    variant="outline"
                    @click="cancelRequest(row.id)"
                  >
                    Cancel request
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <form class="mt-4 grid max-w-lg gap-3" @submit.prevent="submitRequest">
            <h3 class="m-0">Submit a request</h3>
            <label class="grid gap-1 text-sm font-medium">
              Leave type
              <NativeSelect v-model="leaveType" class="w-full">
                <NativeSelectOption v-for="type in LEAVE_TYPES" :key="type" :value="type">
                  {{ type }}
                </NativeSelectOption>
              </NativeSelect>
            </label>
            <label class="grid gap-1 text-sm font-medium">
              Starts on
              <Input v-model="startsOn" type="date" required />
            </label>
            <label class="grid gap-1 text-sm font-medium">
              Ends on
              <Input v-model="endsOn" type="date" required />
            </label>
            <label class="grid gap-1 text-sm font-medium">
              Reason
              <Textarea v-model="reason" />
            </label>
            <div v-if="draftKind" class="grid gap-1">
              <StatusBadge :label="draftLabel" :tone="statusTone(draftLabel)" />
              <p class="m-0">Counted days: {{ draftCounted }}</p>
              <p v-if="draftKind === 'draft'" class="m-0 text-[#495057]">
                Balance after approval: {{ remainingForType - draftCounted }}
              </p>
            </div>
            <Button type="submit" :disabled="!canSubmit">
              {{ submitting ? 'Submitting…' : 'Submit request' }}
            </Button>
          </form>
        </div>
      </template>
    </div>
  </section>
</template>
