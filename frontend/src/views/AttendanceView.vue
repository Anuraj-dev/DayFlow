<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

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
import { formatDate, formatDateTime, personLabel } from '@/lib/format'
import { attendanceStatusLabel, exceptionKindLabel, statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type { AttendanceException, AttendanceHome, AttendanceSession } from '@/types/domain'

const session = useSessionStore()
const data = ref<AttendanceHome | null>(null)
const error = ref('')
const actionError = ref('')
const actionStatus = ref('')
const loading = ref(true)

const kindFilter = ref<'all' | 'missing_check_out' | 'correction_pending'>('all')
const personFilter = ref('')
const correctionOpen = ref(false)
const correctionSessionId = ref('')
const proposedCheckIn = ref('')
const proposedCheckOut = ref('')
const correctionReason = ref('')
const pendingCorrections = ref<Set<string>>(new Set())
const selectedExceptionId = ref('')
const reviewComment = ref('')
const reviewing = ref(false)

const todayLabel = computed(() => {
  if (data.value?.open_session) return 'Checked in'
  const today = data.value?.sessions.find((row) => row.id && row.check_out_at)
  if (today) return 'Checked out'
  return attendanceStatusLabel('not_checked_in')
})

const visibleExceptions = computed(() => {
  const rows = data.value?.exceptions ?? []
  const term = personFilter.value.trim().toLowerCase()
  return rows.filter((row) => {
    if (kindFilter.value !== 'all' && row.kind !== kindFilter.value) return false
    if (!term) return true
    return `${row.employee_name ?? ''} ${row.employee_id ?? ''}`.toLowerCase().includes(term)
  })
})

const selectedException = computed(() =>
  visibleExceptions.value.find((row) => row.id === selectedExceptionId.value) ?? visibleExceptions.value[0] ?? null,
)

onMounted(async () => {
  try {
    const home = await api<AttendanceHome>('/api/attendance')
    data.value = home
    if (!correctionSessionId.value) {
      correctionSessionId.value = home.sessions[0]?.id ?? ''
    }
    selectedExceptionId.value = home.exceptions[0]?.id ?? ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load attendance.'
  } finally {
    loading.value = false
  }
})

function sessionLabel(row: AttendanceSession): string {
  const pending =
    pendingCorrections.value.has(row.id) ||
    ['PENDING', 'pending', 'correction_requested'].includes(row.correction_status ?? '')
  if (pending) return 'Correction requested'
  if (data.value?.open_session?.id === row.id) return 'Checked in'
  if (!row.check_out_at && (!row.status || row.status.toUpperCase() === 'OPEN')) {
    return 'Missing check-out'
  }
  return attendanceStatusLabel(row.status)
}

function exceptionStatusLabel(row: AttendanceException): string {
  if (row.kind === 'missing_check_out') return 'Missing check-out'
  return attendanceStatusLabel(row.status || row.kind)
}

async function punch(path: '/api/attendance/check-in' | '/api/attendance/check-out') {
  actionError.value = ''
  actionStatus.value = ''
  try {
    await api(path, { method: 'POST' })
    data.value = await api('/api/attendance')
    actionStatus.value = path.endsWith('check-in') ? 'Checked in successfully.' : 'Checked out successfully.'
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Attendance action failed.'
  }
}

function openCorrection(sessionId?: string) {
  actionError.value = ''
  actionStatus.value = ''
  correctionOpen.value = true
  correctionSessionId.value = sessionId || data.value?.sessions[0]?.id || ''
  const row = data.value?.sessions.find((item) => item.id === correctionSessionId.value)
  proposedCheckIn.value = toDateTimeLocal(row?.check_in_at)
  proposedCheckOut.value = toDateTimeLocal(row?.check_out_at)
}

function toDateTimeLocal(value: string | null | undefined): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.slice(0, 16)
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

function toApiDateTime(value: string): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toISOString()
}

async function submitCorrection() {
  actionError.value = ''
  actionStatus.value = ''
  const reason = correctionReason.value.trim()
  if (!correctionSessionId.value) {
    actionError.value = 'Select a session to correct.'
    return
  }
  if (!reason) {
    actionError.value = 'A reason is required.'
    return
  }
  try {
    await api('/api/attendance/corrections', {
      method: 'POST',
      body: JSON.stringify({
        attendance_session_id: correctionSessionId.value,
        proposed_check_in_at: toApiDateTime(proposedCheckIn.value),
        proposed_check_out_at: toApiDateTime(proposedCheckOut.value),
        reason,
      }),
    })
    pendingCorrections.value = new Set([...pendingCorrections.value, correctionSessionId.value])
    correctionOpen.value = false
    correctionReason.value = ''
    data.value = await api('/api/attendance')
    actionStatus.value = 'Correction request sent to HR.'
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not request a correction.'
  }
}

async function reviewCorrection(decision: 'APPROVED' | 'REJECTED') {
  const row = selectedException.value
  actionError.value = ''
  actionStatus.value = ''
  if (!row || row.kind !== 'correction_pending') return
  if (decision === 'REJECTED' && !reviewComment.value.trim()) {
    actionError.value = 'Add a comment before rejecting this correction.'
    return
  }
  reviewing.value = true
  try {
    await api(`/api/attendance/corrections/${row.id}/review`, {
      method: 'POST',
      body: JSON.stringify({ decision, comment: reviewComment.value.trim() || null }),
    })
    const home = await api<AttendanceHome>('/api/attendance')
    data.value = home
    selectedExceptionId.value = home.exceptions[0]?.id ?? ''
    reviewComment.value = ''
    actionStatus.value = decision === 'APPROVED' ? 'Correction approved and attendance updated.' : 'Correction rejected.'
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not review this correction.'
  } finally {
    reviewing.value = false
  }
}
</script>

<template>
  <section class="sheet">
    <PageHeader
      :title="session.isHr ? 'Attendance review' : 'Attendance'"
      :description="
        session.isHr
          ? 'Resolve missing check-outs and correction requests.'
          : 'Check in and inspect the week. Corrections go to HR.'
      "
    />
    <Teleport v-if="!session.isHr" defer to="#control-actions">
      <div class="flex items-center gap-2">
        <Button type="button" :disabled="loading || Boolean(data?.open_session)" @click="punch('/api/attendance/check-in')">
          Check in
        </Button>
        <Button
          type="button"
          variant="outline"
          :disabled="loading || !data?.open_session"
          @click="punch('/api/attendance/check-out')"
        >
          Check out
        </Button>
      </div>
    </Teleport>
    <p v-if="loading">Loading attendance…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <div v-else>
      <p v-if="actionError" class="feedback-error" role="alert">{{ actionError }}</p>
      <p v-if="actionStatus" class="feedback-success" role="status">{{ actionStatus }}</p>
      <div v-if="!session.isHr" class="mb-4">
        <h2 class="mt-0">Today</h2>
        <StatusBadge :label="todayLabel" :tone="statusTone(todayLabel)" />
        <div class="mt-3 flex flex-wrap gap-2">
          <Button type="button" variant="outline" :disabled="!data?.sessions.length" @click="openCorrection()">
            Request correction
          </Button>
        </div>
        <form v-if="correctionOpen" class="mt-4 grid max-w-xl gap-3" @submit.prevent="submitCorrection">
          <label class="grid gap-1 text-sm font-medium">
            Session
            <NativeSelect v-model="correctionSessionId" class="w-full">
              <NativeSelectOption v-for="row in data?.sessions ?? []" :key="row.id" :value="row.id">
                {{ row.work_date ?? row.id }}
              </NativeSelectOption>
            </NativeSelect>
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Proposed check in
            <Input v-model="proposedCheckIn" type="datetime-local" required />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Proposed check out
            <Input v-model="proposedCheckOut" type="datetime-local" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Reason
            <Textarea v-model="correctionReason" rows="3" />
          </label>
          <div class="flex gap-2">
            <Button type="submit">Submit correction</Button>
            <Button type="button" variant="outline" @click="correctionOpen = false">Cancel</Button>
          </div>
        </form>
      </div>
      <div v-if="session.isHr" class="mb-3 flex flex-wrap gap-3">
        <label class="grid max-w-xs min-w-48 flex-1 gap-1 text-sm font-medium">
          Person
          <Input v-model="personFilter" type="search" />
        </label>
        <label class="grid w-56 gap-1 text-sm font-medium">
          Exception
          <NativeSelect v-model="kindFilter" class="w-full">
            <NativeSelectOption value="all">All</NativeSelectOption>
            <NativeSelectOption value="missing_check_out">Missing check-out</NativeSelectOption>
            <NativeSelectOption value="correction_pending">Correction requested</NativeSelectOption>
          </NativeSelect>
        </label>
      </div>
      <EmptyState
        v-if="session.isHr && !data?.exceptions.length"
        title="No exceptions"
        body="Missing check-outs and corrections appear here for review."
      />
      <EmptyState
        v-else-if="session.isHr && visibleExceptions.length === 0"
        title="No results"
        body="No exceptions match this filter."
      >
        <Button
          type="button"
          variant="outline"
          class="mt-3"
          @click="personFilter = ''; kindFilter = 'all'"
        >
          Clear filters
        </Button>
      </EmptyState>
      <Table v-else-if="session.isHr">
        <TableCaption class="sr-only">Attendance exceptions</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Exception</TableHead>
            <TableHead>Person</TableHead>
            <TableHead>Status</TableHead>
            <TableHead class="text-right">Review</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="row in visibleExceptions" :key="row.id">
            <TableCell>{{ exceptionKindLabel(row.kind) }}</TableCell>
            <TableCell>
              <RouterLink
                v-if="row.employee_id"
                class="text-[#017E84] underline"
                :to="`/employees/${row.employee_id}`"
              >
                {{ personLabel(row.employee_name) }}
              </RouterLink>
              <span v-else>{{ personLabel(row.employee_name) }}</span>
            </TableCell>
            <TableCell>
              <StatusBadge
                :label="exceptionStatusLabel(row)"
                :tone="statusTone(exceptionStatusLabel(row))"
              />
            </TableCell>
            <TableCell class="text-right">
              <Button
                type="button"
                size="sm"
                :variant="selectedException?.id === row.id ? 'default' : 'outline'"
                @click="selectedExceptionId = row.id; reviewComment = ''"
              >
                {{ selectedException?.id === row.id ? 'Selected' : 'Review' }}
              </Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <section v-if="session.isHr && selectedException" class="mt-5 border-t border-[#d8d8d8] pt-5" aria-labelledby="attendance-review-title">
        <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.65fr)]">
          <div>
            <p class="eyebrow mb-1">Selected exception</p>
            <h2 id="attendance-review-title" class="mt-0">{{ exceptionKindLabel(selectedException.kind) }}</h2>
            <dl class="grid gap-2 text-sm sm:grid-cols-2">
              <div><dt class="text-muted-foreground">Person</dt><dd class="m-0 font-medium">{{ personLabel(selectedException.employee_name) }}</dd></div>
              <div><dt class="text-muted-foreground">Work date</dt><dd class="m-0 font-medium">{{ formatDate(selectedException.work_date) }}</dd></div>
              <div><dt class="text-muted-foreground">Current check in</dt><dd class="m-0 font-medium">{{ formatDateTime(selectedException.current_check_in_at) }}</dd></div>
              <div><dt class="text-muted-foreground">Current check out</dt><dd class="m-0 font-medium">{{ formatDateTime(selectedException.current_check_out_at) }}</dd></div>
              <template v-if="selectedException.kind === 'correction_pending'">
                <div><dt class="text-muted-foreground">Proposed check in</dt><dd class="m-0 font-medium">{{ formatDateTime(selectedException.proposed_check_in_at) }}</dd></div>
                <div><dt class="text-muted-foreground">Proposed check out</dt><dd class="m-0 font-medium">{{ formatDateTime(selectedException.proposed_check_out_at) }}</dd></div>
              </template>
            </dl>
            <p v-if="selectedException.reason" class="mt-3 text-sm"><strong>Reason:</strong> {{ selectedException.reason }}</p>
          </div>
          <div v-if="selectedException.kind === 'correction_pending'" class="grid content-start gap-3">
            <label class="grid gap-1 text-sm font-medium">
              Review comment <span class="font-normal text-muted-foreground">(required to reject)</span>
              <Textarea v-model="reviewComment" rows="3" maxlength="500" placeholder="Add decision context for the audit trail" />
            </label>
            <div class="flex flex-wrap gap-2">
              <Button type="button" :disabled="reviewing" @click="reviewCorrection('APPROVED')">Approve correction</Button>
              <Button type="button" variant="destructive" :disabled="reviewing" @click="reviewCorrection('REJECTED')">Reject correction</Button>
            </div>
          </div>
          <p v-else class="m-0 self-start border-l-4 border-[#e0a800] bg-[#fff8dc] p-3 text-sm">
            Ask the employee to submit a correction request. Historical punches change only after HR reviews that request.
          </p>
        </div>
      </section>
      <template v-if="!session.isHr">
        <h2>This week</h2>
        <div class="hidden sm:block">
          <Table>
            <TableCaption class="sr-only">This week</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Work date</TableHead>
                <TableHead>Check in</TableHead>
                <TableHead>Check out</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="!data?.sessions.length">
                <TableCell colspan="4">No sessions this week.</TableCell>
              </TableRow>
              <TableRow v-for="row in data?.sessions ?? []" :key="row.id">
                <TableCell>{{ formatDate(row.work_date) }}</TableCell>
                <TableCell>{{ formatDateTime(row.check_in_at) }}</TableCell>
                <TableCell>{{ formatDateTime(row.check_out_at) }}</TableCell>
                <TableCell>
                  <StatusBadge :label="sessionLabel(row)" :tone="statusTone(sessionLabel(row))" />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
        <div v-if="data?.sessions.length" class="mobile-record-list">
          <article v-for="row in data.sessions" :key="row.id" class="mobile-record">
            <div class="mobile-record-row">
              <span class="mobile-record-label">Work date</span>
              <strong class="mobile-record-value">{{ formatDate(row.work_date) }}</strong>
            </div>
            <div class="mobile-record-row">
              <span class="mobile-record-label">Check in</span>
              <span class="mobile-record-value">{{ formatDateTime(row.check_in_at) }}</span>
            </div>
            <div class="mobile-record-row">
              <span class="mobile-record-label">Check out</span>
              <span class="mobile-record-value">{{ formatDateTime(row.check_out_at) }}</span>
            </div>
            <StatusBadge :label="sessionLabel(row)" :tone="statusTone(sessionLabel(row))" />
          </article>
        </div>
        <EmptyState v-else title="No sessions this week" body="Your attendance sessions will appear here." />
      </template>
    </div>
  </section>
</template>
