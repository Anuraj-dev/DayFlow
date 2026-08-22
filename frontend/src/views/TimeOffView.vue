<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'

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
import { api, getToken, HttpError } from '@/api/client'
import { formatDate } from '@/lib/format'
import { countedWorkdays, isBlockingLeaveStatus, leaveRequiresBalance, rangesOverlap } from '@/lib/leave'
import { leaveStatusLabel, leaveTypeLabel, statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type { LeaveBalance, LeaveRequest, TimeOffHome } from '@/types/domain'

const LEAVE_TYPES = ['PAID', 'SICK', 'UNPAID'] as const

const session = useSessionStore()
const data = ref<TimeOffHome | null>(null)
const error = ref('')
const actionError = ref('')
const actionStatus = ref('')
const loading = ref(true)
const controlActionsReady = ref(false)
const leaveType = ref<(typeof LEAVE_TYPES)[number]>('PAID')
const startsOn = ref('')
const endsOn = ref('')
const reason = ref('')
const certificateFile = ref<File | null>(null)
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

function usedDays(row: LeaveBalance): number {
  if (typeof row.used_days === 'number') return row.used_days
  if (typeof row.granted_days === 'number') return Math.max(0, row.granted_days - row.remaining_days)
  return 0
}

function requestConflicts(row: LeaveRequest): boolean {
  return (data.value?.requests ?? []).some(
    (other) =>
      other.id !== row.id &&
      (other.employee_id ?? '') === (row.employee_id ?? '') &&
      isBlockingLeaveStatus(other.status) &&
      rangesOverlap(row.starts_on, row.ends_on, other.starts_on, other.ends_on),
  )
}

function dateRangeLabel(starts: string, ends: string): string {
  return `${formatDate(starts)} – ${formatDate(ends)}`
}

function selectPending(id: string) {
  selectedRequestId.value = id
  actionError.value = ''
}

function focusRequestForm() {
  document.getElementById('new-leave-request')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  window.setTimeout(() => {
    const field = document.querySelector<HTMLElement>('#new-leave-request select, #new-leave-request input')
    field?.focus()
  }, 200)
}

async function loadHome() {
  data.value = await api<TimeOffHome>('/api/time-off')
  if (session.isHr && !data.value.pending_queue.some((row) => row.id === selectedRequestId.value)) {
    selectedRequestId.value = data.value.pending_queue[0]?.id ?? ''
  }
  if (pendingPage.value > pendingPageCount.value) {
    pendingPage.value = pendingPageCount.value
  }
}

onMounted(async () => {
  await nextTick()
  controlActionsReady.value = Boolean(document.getElementById('control-actions'))
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
    if (leaveType.value === 'SICK' && certificateFile.value) {
      const form = new FormData()
      form.append('leave_type', leaveType.value)
      form.append('starts_on', startsOn.value)
      form.append('ends_on', endsOn.value)
      form.append('reason', reason.value.trim())
      form.append('certificate', certificateFile.value)
      await api('/api/time-off/requests', { method: 'POST', body: form })
    } else {
      await api('/api/time-off/requests', {
        method: 'POST',
        body: JSON.stringify({
          leave_type: leaveType.value,
          starts_on: startsOn.value,
          ends_on: endsOn.value,
          reason: reason.value.trim(),
        }),
      })
    }
    startsOn.value = ''
    endsOn.value = ''
    reason.value = ''
    certificateFile.value = null
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

async function openCertificate(row: LeaveRequest) {
  const path = row.certificate_download_url ?? `/api/time-off/requests/${row.id}/certificate`
  try {
    const headers = new Headers({ Accept: '*/*' })
    const token = getToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const response = await fetch(path, { headers })
    if (!response.ok) {
      actionError.value = 'Could not download certificate.'
      return
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank', 'noopener')
  } catch {
    actionError.value = 'Could not download certificate.'
  }
}

function onCertificateChange(event: Event) {
  const input = event.target as HTMLInputElement
  certificateFile.value = input.files?.[0] ?? null
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
    <Teleport v-if="controlActionsReady && !session.isHr" defer to="#control-actions">
      <div class="flex items-center gap-2">
        <Button type="button" @click="focusRequestForm">New Request</Button>
      </div>
    </Teleport>

    <PageHeader
      v-if="session.isHr"
      title="Leave approvals"
      description="Review pending leave with balance and overlap context."
    />

    <p v-if="loading">Loading time off…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <div v-else class="time-off-body">
      <p v-if="actionError" class="feedback-error" role="alert">{{ actionError }}</p>
      <p v-if="actionStatus" class="feedback-success" role="status">{{ actionStatus }}</p>

      <div v-if="session.isHr" class="grid gap-4">
        <div class="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 class="section-heading">Pending requests</h2>
            <p class="m-0 mt-1 text-sm text-[#495057]">
              {{ data?.pending_queue.length ?? 0 }} awaiting review
            </p>
          </div>
          <div v-if="(data?.pending_queue.length ?? 0) > PENDING_PAGE_SIZE" class="flex gap-2">
            <Button type="button" size="sm" variant="outline" :disabled="pendingPage === 1" @click="pendingPage--">
              Previous
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              :disabled="pendingPage === pendingPageCount"
              @click="pendingPage++"
            >
              Next
            </Button>
          </div>
        </div>

        <EmptyState
          v-if="!data?.pending_queue.length"
          title="No pending requests"
          body="Rejection requires a comment. Approval updates balance and attendance in one transaction."
        />
        <template v-else>
          <div class="hidden sm:block overflow-x-auto">
            <Table>
              <TableCaption class="sr-only">Pending leave requests</TableCaption>
              <TableHeader class="sticky top-0 bg-white">
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Dates</TableHead>
                  <TableHead>Days</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow
                  v-for="row in pagedPending"
                  :key="row.id"
                  class="cursor-pointer"
                  :data-selected="selectedRequestId === row.id"
                  :aria-selected="selectedRequestId === row.id"
                  @click="selectPending(row.id)"
                >
                  <TableCell class="font-medium">{{ row.employee_name ?? 'Employee' }}</TableCell>
                  <TableCell>{{ leaveTypeLabel(row.leave_type) }}</TableCell>
                  <TableCell>
                    {{ formatDate(row.starts_on) }} to {{ formatDate(row.ends_on) }}
                  </TableCell>
                  <TableCell>{{ row.counted_days ?? '—' }}</TableCell>
                  <TableCell>
                    <StatusBadge
                      :label="leaveStatusLabel(row.status)"
                      :tone="statusTone(leaveStatusLabel(row.status))"
                    />
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>

          <div class="mobile-record-list">
            <button
              v-for="row in pagedPending"
              :key="row.id"
              type="button"
              class="mobile-record w-full border-0 bg-transparent p-4 text-left"
              :data-selected="selectedRequestId === row.id"
              :aria-selected="selectedRequestId === row.id"
              @click="selectPending(row.id)"
            >
              <div class="mobile-record-row">
                <strong>{{ row.employee_name ?? 'Employee' }}</strong>
                <StatusBadge
                  :label="leaveStatusLabel(row.status)"
                  :tone="statusTone(leaveStatusLabel(row.status))"
                />
              </div>
              <p class="m-0 text-sm text-[#495057]">
                {{ leaveTypeLabel(row.leave_type) }} · {{ row.counted_days ?? '—' }} days
              </p>
              <p class="m-0">{{ formatDate(row.starts_on) }} to {{ formatDate(row.ends_on) }}</p>
            </button>
          </div>

          <section
            v-if="selectedRequest"
            class="border-t border-[#DEE2E6] pt-5"
            aria-labelledby="leave-review-title"
          >
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 id="leave-review-title" class="section-heading">Selected request</h2>
                <p class="m-0 mt-1 text-[#495057]">
                  {{ selectedRequest.employee_name ?? 'Employee' }} ·
                  {{ leaveTypeLabel(selectedRequest.leave_type) }} ·
                  {{ formatDate(selectedRequest.starts_on) }} to {{ formatDate(selectedRequest.ends_on) }}
                  · {{ selectedRequest.counted_days ?? '—' }} days
                </p>
              </div>
              <StatusBadge
                :label="leaveStatusLabel(selectedRequest.status)"
                :tone="statusTone(leaveStatusLabel(selectedRequest.status))"
              />
            </div>

            <p
              v-if="requestConflicts(selectedRequest)"
              class="feedback-error mt-4 mb-0"
              role="status"
            >
              Conflict: this range overlaps another pending or approved request for the same employee.
            </p>

            <p v-if="selectedRequest.reason" class="mt-4 mb-0">
              <span class="text-sm font-medium">Reason</span><br />
              {{ selectedRequest.reason }}
            </p>
            <p v-if="selectedRequest.has_certificate" class="mt-4 mb-0">
              <Button type="button" variant="outline" @click="openCertificate(selectedRequest)">
                Download certificate
              </Button>
            </p>

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
              <Button type="button" @click="decide(selectedRequest.id, 'approve')">Approve</Button>
              <Button
                type="button"
                variant="destructive"
                @click="decide(selectedRequest.id, 'reject')"
              >
                Reject
              </Button>
            </div>
          </section>
        </template>
      </div>

      <template v-else>
        <section aria-labelledby="balance-title">
          <h2 id="balance-title" class="section-heading mb-3">Balance</h2>
          <div class="hidden sm:block overflow-x-auto">
            <Table>
              <TableCaption class="sr-only">Leave balances</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Remaining</TableHead>
                  <TableHead>Used</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-if="!data?.balances.length">
                  <TableCell colspan="3">No balances yet</TableCell>
                </TableRow>
                <TableRow v-for="row in data?.balances ?? []" :key="row.leave_type">
                  <TableCell class="font-medium">{{ leaveTypeLabel(row.leave_type) }}</TableCell>
                  <TableCell>{{ row.remaining_days }}</TableCell>
                  <TableCell>{{ usedDays(row) }}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
          <div v-if="data?.balances.length" class="mobile-record-list">
            <div v-for="row in data.balances" :key="row.leave_type" class="mobile-record">
              <div class="mobile-record-row">
                <span class="mobile-record-label">{{ leaveTypeLabel(row.leave_type) }}</span>
                <strong class="mobile-record-value">{{ row.remaining_days }} remaining</strong>
              </div>
              <p class="m-0 text-sm text-[#495057]">{{ usedDays(row) }} used</p>
            </div>
          </div>
        </section>

        <section aria-labelledby="requests-title">
          <h2 id="requests-title" class="section-heading mb-3">My requests</h2>
          <div class="hidden sm:block overflow-x-auto">
            <Table>
              <TableCaption class="sr-only">Leave requests</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Dates</TableHead>
                  <TableHead>Days</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead class="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-if="!data?.requests.length">
                  <TableCell colspan="5">No requests yet</TableCell>
                </TableRow>
                <TableRow v-for="row in data?.requests ?? []" :key="row.id">
                  <TableCell class="font-medium">{{ leaveTypeLabel(row.leave_type) }}</TableCell>
                  <TableCell>{{ dateRangeLabel(row.starts_on, row.ends_on) }}</TableCell>
                  <TableCell>{{ row.counted_days ?? '—' }}</TableCell>
                  <TableCell>
                    <StatusBadge
                      :label="leaveStatusLabel(row.status)"
                      :tone="statusTone(leaveStatusLabel(row.status))"
                    />
                  </TableCell>
                  <TableCell class="text-right">
                    <Button
                      v-if="row.status.toUpperCase() === 'PENDING'"
                      type="button"
                      size="sm"
                      variant="outline"
                      @click="cancelRequest(row.id)"
                    >
                      Cancel
                    </Button>
                    <span v-else class="text-[#495057]">—</span>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>
          <div v-if="data?.requests.length" class="mobile-record-list">
            <article v-for="row in data.requests" :key="row.id" class="mobile-record">
              <div class="mobile-record-row">
                <strong>{{ leaveTypeLabel(row.leave_type) }}</strong>
                <StatusBadge
                  :label="leaveStatusLabel(row.status)"
                  :tone="statusTone(leaveStatusLabel(row.status))"
                />
              </div>
              <p class="m-0">{{ formatDate(row.starts_on) }} to {{ formatDate(row.ends_on) }}</p>
              <p class="m-0 text-[#495057]">{{ row.counted_days ?? '—' }} counted days</p>
              <Button
                v-if="row.status.toUpperCase() === 'PENDING'"
                type="button"
                variant="outline"
                @click="cancelRequest(row.id)"
              >
                Cancel
              </Button>
            </article>
          </div>
          <EmptyState
            v-else-if="!data?.requests.length"
            class="sm:hidden"
            title="No requests yet"
            body="Submit a leave request below. Pending requests can be cancelled."
          />
        </section>

        <form
          id="new-leave-request"
          class="grid max-w-2xl gap-3 border-t border-[#DEE2E6] pt-5"
          @submit.prevent="submitRequest"
        >
          <h2 class="section-heading">New leave request</h2>
          <label class="grid gap-1 text-sm font-medium">
            Leave type
            <NativeSelect v-model="leaveType" class="w-full">
              <NativeSelectOption v-for="type in LEAVE_TYPES" :key="type" :value="type">
                {{ leaveTypeLabel(type) }}
              </NativeSelectOption>
            </NativeSelect>
          </label>
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="grid gap-1 text-sm font-medium">
              Starts on
              <Input v-model="startsOn" type="date" required />
            </label>
            <label class="grid gap-1 text-sm font-medium">
              Ends on
              <Input v-model="endsOn" type="date" required />
            </label>
          </div>
          <label class="grid gap-1 text-sm font-medium">
            Reason
            <Textarea v-model="reason" rows="3" maxlength="500" placeholder="Required. Explain the reason for this request." />
          </label>
          <label v-if="leaveType === 'SICK'" class="grid gap-1 text-sm font-medium">
            Certificate
            <Input type="file" accept="application/pdf,image/jpeg,image/png,.pdf,.jpg,.jpeg,.png" @change="onCertificateChange" />
          </label>
          <div v-if="draftKind" class="grid gap-1">
            <StatusBadge :label="draftLabel" :tone="statusTone(draftLabel)" />
            <p class="m-0">Counted days: {{ draftCounted }}</p>
            <p v-if="draftKind === 'draft'" class="m-0 text-[#495057]">
              Balance after approval: {{ remainingForType - draftCounted }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <Button type="submit" :disabled="!canSubmit">
              {{ submitting ? 'Submitting…' : 'Submit request' }}
            </Button>
            <p v-if="!canSubmit && startsOn && endsOn" class="m-0 text-sm text-[#495057]">
              Add a reason and resolve any balance or date conflict before submitting.
            </p>
          </div>
        </form>
      </template>
    </div>
  </section>
</template>

<style scoped>
.time-off-body {
  display: grid;
  gap: 1.5rem;
}

.section-heading {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
  color: #212529;
}

[data-selected='true'] {
  background: color-mix(in srgb, #714b67 8%, white);
}
</style>
