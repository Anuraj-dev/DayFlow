<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

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
import { formatDate } from '@/lib/format'
import { countedWorkdays, isBlockingLeaveStatus, leaveRequiresBalance, rangesOverlap } from '@/lib/leave'
import { leaveStatusLabel, leaveTypeLabel, statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type { LeaveRequest, TimeOffHome } from '@/types/domain'

const LEAVE_TYPES = ['PAID', 'SICK', 'UNPAID'] as const

const session = useSessionStore()
const data = ref<TimeOffHome | null>(null)
const error = ref('')
const actionError = ref('')
const actionStatus = ref('')
const loading = ref(true)
const leaveType = ref<(typeof LEAVE_TYPES)[number]>('PAID')
const startsOn = ref('')
const endsOn = ref('')
const reason = ref('')
const submitting = ref(false)
const reviewComments = reactive<Record<string, string>>({})
const selectedRequestId = ref('')
const pendingPage = ref(1)
const PENDING_PAGE_SIZE = 15

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

const selectedRequest = computed(() =>
  (data.value?.pending_queue ?? []).find((row) => row.id === selectedRequestId.value) ?? null,
)

const pendingPageCount = computed(() =>
  Math.max(1, Math.ceil((data.value?.pending_queue.length ?? 0) / PENDING_PAGE_SIZE)),
)

const pagedPending = computed(() => {
  const start = (pendingPage.value - 1) * PENDING_PAGE_SIZE
  return (data.value?.pending_queue ?? []).slice(start, start + PENDING_PAGE_SIZE)
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
  if (session.isHr && !data.value.pending_queue.some((row) => row.id === selectedRequestId.value)) {
    selectedRequestId.value = data.value.pending_queue[0]?.id ?? ''
  }
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
  actionStatus.value = ''
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
    actionStatus.value = 'Leave request submitted for HR review.'
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not submit leave.'
  } finally {
    submitting.value = false
  }
}

async function decide(id: string, decision: 'approve' | 'reject') {
  actionError.value = ''
  actionStatus.value = ''
  const comment = (reviewComments[id] ?? '').trim()
  if (decision === 'reject' && !comment) {
    actionError.value = 'Rejection requires a comment.'
    return
  }
  try {
    await api(`/api/time-off/requests/${id}/${decision}`, {
      method: 'POST',
      body: JSON.stringify({ comment: comment || null }),
    })
    delete reviewComments[id]
    await loadHome()
    actionStatus.value = decision === 'approve' ? 'Leave request approved.' : 'Leave request rejected.'
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not update leave.'
  }
}

async function cancelRequest(id: string) {
  actionError.value = ''
  actionStatus.value = ''
  try {
    await api(`/api/time-off/requests/${id}/cancel`, { method: 'POST' })
    await loadHome()
    actionStatus.value = 'Leave request cancelled.'
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
      <p v-if="actionError" class="feedback-error" role="alert">{{ actionError }}</p>
      <p v-if="actionStatus" class="feedback-success" role="status">{{ actionStatus }}</p>

      <div v-if="session.isHr">
        <h2 class="mt-0">Pending queue</h2>
        <EmptyState
          v-if="!data?.pending_queue.length"
          title="No pending requests"
          body="Rejection requires a comment. Approval updates balance and attendance in one transaction."
        />
        <template v-else>
          <div class="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm text-[#495057]">
            <p class="m-0">{{ data?.pending_queue.length }} requests awaiting review</p>
            <div class="flex gap-2">
              <Button type="button" size="sm" variant="outline" :disabled="pendingPage === 1" @click="pendingPage--">Previous</Button>
              <Button type="button" size="sm" variant="outline" :disabled="pendingPage === pendingPageCount" @click="pendingPage++">Next</Button>
            </div>
          </div>
          <Table>
            <TableCaption class="sr-only">Pending leave requests</TableCaption>
            <TableHeader class="sticky top-0 bg-white">
              <TableRow>
                <TableHead>Employee</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Dates</TableHead>
                <TableHead>Days</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Review</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="row in pagedPending" :key="row.id" :data-selected="selectedRequestId === row.id">
                <TableCell>{{ row.employee_name ?? 'Employee' }}</TableCell>
                <TableCell>{{ leaveTypeLabel(row.leave_type) }}</TableCell>
                <TableCell>{{ formatDate(row.starts_on) }} to {{ formatDate(row.ends_on) }}</TableCell>
                <TableCell>{{ row.counted_days ?? '—' }}</TableCell>
                <TableCell>
                  <StatusBadge :label="leaveStatusLabel(row.status)" :tone="statusTone(leaveStatusLabel(row.status))" />
                </TableCell>
                <TableCell>
                  <Button type="button" size="sm" variant="outline" @click="selectedRequestId = row.id">
                    {{ selectedRequestId === row.id ? 'Selected' : 'Review' }}
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>

          <section v-if="selectedRequest" class="mt-5 border-t border-border pt-5" aria-labelledby="leave-review-title">
            <h2 id="leave-review-title" class="mt-0">Review {{ selectedRequest.employee_name ?? 'employee request' }}</h2>
            <div class="grid gap-3 sm:grid-cols-2">
              <p class="m-0"><strong>Type</strong><br>{{ leaveTypeLabel(selectedRequest.leave_type) }}</p>
              <p class="m-0"><strong>Dates</strong><br>{{ formatDate(selectedRequest.starts_on) }} to {{ formatDate(selectedRequest.ends_on) }}</p>
              <p class="m-0"><strong>Counted days</strong><br>{{ selectedRequest.counted_days ?? 'Not calculated' }}</p>
              <p class="m-0"><strong>Overlap</strong><br>{{ requestConflicts(selectedRequest) ? 'Conflict found' : 'No overlap' }}</p>
            </div>
            <p v-if="selectedRequest.reason" class="mt-3 mb-0"><strong>Employee reason</strong><br>{{ selectedRequest.reason }}</p>
            <label class="mt-4 grid max-w-xl gap-1 text-sm font-medium">
              Review comment
              <Textarea
                v-model="reviewComments[selectedRequest.id]"
                rows="3"
                maxlength="500"
                placeholder="Required when rejecting."
              />
            </label>
            <div class="mt-3 flex flex-wrap gap-2">
              <Button type="button" variant="outline" @click="decide(selectedRequest.id, 'approve')">Approve request</Button>
              <Button type="button" variant="destructive" @click="decide(selectedRequest.id, 'reject')">Reject request</Button>
            </div>
          </section>
        </template>
      </div>

      <template v-else>
        <div class="hidden sm:block">
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
              <TableCell>{{ leaveTypeLabel(row.leave_type) }}</TableCell>
              <TableCell>{{ row.remaining_days }}</TableCell>
            </TableRow>
          </TableBody>
          </Table>
        </div>
        <div v-if="data?.balances.length" class="mobile-record-list">
          <div v-for="row in data.balances" :key="row.leave_type" class="mobile-record mobile-record-row">
            <span>{{ leaveTypeLabel(row.leave_type) }}</span>
            <strong>{{ row.remaining_days }} days</strong>
          </div>
        </div>

        <div>
          <h2>Requests</h2>
          <div class="hidden sm:block">
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
                <TableCell>{{ leaveTypeLabel(row.leave_type) }}</TableCell>
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
          </div>
          <div v-if="data?.requests.length" class="mobile-record-list">
            <article v-for="row in data.requests" :key="row.id" class="mobile-record">
              <div class="mobile-record-row">
                <strong>{{ leaveTypeLabel(row.leave_type) }}</strong>
                <StatusBadge :label="leaveStatusLabel(row.status)" :tone="statusTone(leaveStatusLabel(row.status))" />
              </div>
              <p class="m-0">{{ formatDate(row.starts_on) }} to {{ formatDate(row.ends_on) }}</p>
              <p class="m-0 text-[#495057]">{{ row.counted_days ?? '—' }} counted days</p>
              <Button
                v-if="row.status.toUpperCase() === 'PENDING'"
                type="button"
                variant="outline"
                @click="cancelRequest(row.id)"
              >
                Cancel request
              </Button>
            </article>
          </div>
          <form class="mt-4 grid max-w-lg gap-3" @submit.prevent="submitRequest">
            <h3 class="m-0">Submit a request</h3>
            <label class="grid gap-1 text-sm font-medium">
              Leave type
              <NativeSelect v-model="leaveType" class="w-full">
                <NativeSelectOption v-for="type in LEAVE_TYPES" :key="type" :value="type">
                  {{ leaveTypeLabel(type) }}
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
              <Textarea v-model="reason" maxlength="500" placeholder="Explain the reason for this request." />
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
            <p v-if="!canSubmit && startsOn && endsOn" class="m-0 text-sm text-[#495057]">
              Add a reason and resolve any balance or date conflict before submitting.
            </p>
          </form>
        </div>
      </template>
    </div>
  </section>
</template>
