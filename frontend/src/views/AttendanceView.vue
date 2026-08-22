<script setup lang="ts">
import { CalendarDaysIcon, CircleAlertIcon, Clock3Icon } from '@lucide/vue'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
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
import { useAttendanceStore } from '@/stores/attendance'
import { useSessionStore } from '@/stores/session'
import type { AttendanceException, AttendanceHome, AttendanceSession } from '@/types/domain'

const session = useSessionStore()
const attendance = useAttendanceStore()
const page = ref<AttendanceHome | null>(null)
const selectedMonth = ref('')
const pageLoading = ref(false)
const data = computed(() => page.value)
const error = computed(() => attendance.error)
const loading = computed(() => (attendance.loading || pageLoading.value) && !page.value)
const actionError = ref('')
const actionStatus = ref('')
const controlActionsReady = ref(false)

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

function localDateISO(date = new Date()): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 10)
}

function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, { timeStyle: 'short' }).format(date)
}

function formatWorkedHours(minutes: number | null | undefined): string {
  if (minutes == null || !Number.isFinite(minutes)) return '—'
  const abs = Math.abs(Math.trunc(minutes))
  const hours = Math.floor(abs / 60)
  const mins = abs % 60
  return `${hours}h ${String(mins).padStart(2, '0')}m`
}

function formatLongDate(value: string): string {
  const date = new Date(`${value}T12:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

const todayIso = computed(() => data.value?.today ?? localDateISO())

const todaySession = computed(() => {
  const today = todayIso.value
  return data.value?.sessions.find((row) => row.work_date === today) ?? null
})

const todayLabel = computed(() => {
  if (data.value?.open_session) return 'Checked in'
  if (todaySession.value?.check_out_at) return 'Checked out'
  if (todaySession.value?.status) return attendanceStatusLabel(todaySession.value.status)
  return attendanceStatusLabel('not_checked_in')
})

const todayTone = computed(() => statusTone(todayLabel.value))

const todayCheckIn = computed(
  () => data.value?.open_session?.check_in_at ?? todaySession.value?.check_in_at ?? null,
)

const todayCheckOut = computed(() => todaySession.value?.check_out_at ?? null)

const monthRows = computed(() => {
  if (data.value?.days?.length) return data.value.days
  return data.value?.sessions ?? []
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

const selectedException = computed(
  () =>
    visibleExceptions.value.find((row) => row.id === selectedExceptionId.value) ??
    visibleExceptions.value[0] ??
    null,
)

const exceptionCount = computed(() => data.value?.exceptions.length ?? 0)
const pendingCorrectionCount = computed(
  () => (data.value?.exceptions ?? []).filter((row) => row.kind === 'correction_pending').length,
)
const missingCheckOutCount = computed(
  () => (data.value?.exceptions ?? []).filter((row) => row.kind === 'missing_check_out').length,
)

async function loadPage() {
  pageLoading.value = true
  try {
    const query = selectedMonth.value ? `?month=${encodeURIComponent(selectedMonth.value)}` : ''
    const payload = await api<AttendanceHome>(`/api/attendance${query}`)
    page.value = payload
    if (payload.month && !selectedMonth.value) selectedMonth.value = payload.month
    if (!correctionSessionId.value) {
      correctionSessionId.value = payload.sessions[0]?.id ?? ''
    }
    if (!selectedExceptionId.value) {
      selectedExceptionId.value = payload.exceptions[0]?.id ?? ''
    }
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not load attendance.'
  } finally {
    pageLoading.value = false
  }
}

function shiftMonth(delta: number) {
  const [yearText, monthText] = (selectedMonth.value || '2026-01').split('-')
  const year = Number(yearText)
  const month = Number(monthText)
  const next = new Date(year || 2026, (month || 1) - 1 + delta, 1)
  selectedMonth.value = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`
}

function monthHeading(value: string): string {
  if (!value) return 'This month'
  const date = new Date(`${value}-01T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' }).format(date)
}

function rowStatusLabel(
  row: AttendanceSession | { id?: string; status?: string | null; check_out_at?: string | null; correction_status?: string | null },
): string {
  if ('id' in row && row.id) return sessionLabel(row as AttendanceSession)
  return attendanceStatusLabel(row.status)
}

onMounted(async () => {
  await nextTick()
  controlActionsReady.value = Boolean(document.getElementById('control-actions'))
  await attendance.load()
  await loadPage()
  const home = page.value
  if (!correctionSessionId.value) {
    correctionSessionId.value = home?.sessions[0]?.id ?? ''
  }
  selectedExceptionId.value = home?.exceptions[0]?.id ?? ''
})

watch(
  () => attendance.revision,
  (value, previous) => {
    if (previous !== undefined) void loadPage()
  },
)

watch(selectedMonth, (value, previous) => {
  if (!previous || !value || value === page.value?.month) return
  void loadPage()
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

function selectException(row: AttendanceException) {
  selectedExceptionId.value = row.id
  reviewComment.value = ''
}

function clearExceptionFilters() {
  personFilter.value = ''
  kindFilter.value = 'all'
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
    await attendance.load()
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
    await attendance.load()
    await loadPage()
    selectedExceptionId.value = page.value?.exceptions[0]?.id ?? ''
    reviewComment.value = ''
    actionStatus.value =
      decision === 'APPROVED' ? 'Correction approved and attendance updated.' : 'Correction rejected.'
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not review this correction.'
  } finally {
    reviewing.value = false
  }
}
</script>

<template>
  <section class="sheet attendance-sheet">
    <Teleport v-if="controlActionsReady && !session.isHr" defer to="#control-actions">
      <div class="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          :disabled="loading || !data?.sessions.length"
          @click="openCorrection()"
        >
          Request correction
        </Button>
      </div>
    </Teleport>

    <Teleport v-if="controlActionsReady && session.isHr" defer to="#control-actions">
      <div class="flex w-full min-w-0 flex-wrap items-end gap-2">
        <label class="grid min-w-48 flex-1 gap-1 text-sm font-medium">
          Person
          <Input v-model="personFilter" type="search" placeholder="Search by name" />
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
    </Teleport>

    <p v-if="loading">Loading attendance…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <div v-else class="attendance-body">
      <p v-if="attendance.actionError || actionError" class="feedback-error" role="alert">
        {{ attendance.actionError || actionError }}
      </p>
      <p v-if="actionStatus" class="feedback-success" role="status">{{ actionStatus }}</p>

      <!-- Employee: Today + week -->
      <template v-if="!session.isHr">
        <div v-if="!controlActionsReady" class="mb-4 flex flex-wrap gap-2">
          <Button type="button" variant="outline" :disabled="!data?.sessions.length" @click="openCorrection()">
            Request correction
          </Button>
        </div>

        <div class="employee-layout">
          <section class="today-block" aria-labelledby="today-heading">
            <div class="today-heading-row">
              <div class="section-title">
                <Clock3Icon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
                <h2 id="today-heading" class="mt-0 mb-0">Today</h2>
              </div>
              <StatusBadge :label="todayLabel" :tone="todayTone" />
            </div>
            <p class="today-date">{{ formatLongDate(todayIso) }}</p>
            <dl class="today-details">
              <div>
                <dt>Check in</dt>
                <dd>{{ formatTime(todayCheckIn) }}</dd>
              </div>
              <div>
                <dt>Check out</dt>
                <dd>{{ formatTime(todayCheckOut) }}</dd>
              </div>
            </dl>
          </section>

          <section class="week-block" aria-labelledby="month-heading">
            <div class="week-heading-row">
              <div class="section-title">
                <CalendarDaysIcon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
                <h2 id="month-heading" class="mt-0 mb-0">{{ monthHeading(selectedMonth || data?.month || '') }}</h2>
              </div>
              <div class="flex flex-wrap items-end gap-2">
                <label class="grid w-44 gap-1 text-sm font-medium">
                  Month
                  <Input v-model="selectedMonth" type="month" />
                </label>
                <Button type="button" variant="outline" size="sm" @click="shiftMonth(-1)">Previous month</Button>
                <Button type="button" variant="outline" size="sm" @click="shiftMonth(1)">Next month</Button>
              </div>
            </div>

            <dl v-if="data?.summary" class="today-details mb-3">
              <div>
                <dt>Days present</dt>
                <dd>{{ data.summary.days_present }}</dd>
              </div>
              <div>
                <dt>Leave days</dt>
                <dd>{{ data.summary.leave_days }}</dd>
              </div>
              <div>
                <dt>Scheduled working days</dt>
                <dd>{{ data.summary.scheduled_working_days }}</dd>
              </div>
            </dl>

            <div class="hidden sm:block">
              <Table>
                <TableCaption class="sr-only">Attendance month</TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead>Work date</TableHead>
                    <TableHead>Check in</TableHead>
                    <TableHead>Check out</TableHead>
                    <TableHead>Work hours</TableHead>
                    <TableHead>Extra hours</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow v-if="!monthRows.length">
                    <TableCell colspan="6">No attendance this month.</TableCell>
                  </TableRow>
                  <TableRow v-for="row in monthRows" :key="row.work_date ?? ('id' in row ? row.id : '')">
                    <TableCell>{{ formatDate(row.work_date) }}</TableCell>
                    <TableCell>{{ formatTime(row.check_in_at) }}</TableCell>
                    <TableCell>{{ formatTime(row.check_out_at) }}</TableCell>
                    <TableCell class="tabular-nums">{{ formatWorkedHours(row.worked_minutes) }}</TableCell>
                    <TableCell class="tabular-nums">{{ formatWorkedHours(row.extra_minutes) }}</TableCell>
                    <TableCell>
                      <StatusBadge :label="rowStatusLabel(row)" :tone="statusTone(rowStatusLabel(row))" />
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>

            <div v-if="monthRows.length" class="mobile-record-list">
              <article v-for="row in monthRows" :key="row.work_date ?? ('id' in row ? row.id : '')" class="mobile-record">
                <div class="mobile-record-row">
                  <span class="mobile-record-label">Work date</span>
                  <strong class="mobile-record-value">{{ formatDate(row.work_date) }}</strong>
                </div>
                <div class="mobile-record-row">
                  <span class="mobile-record-label">Check in</span>
                  <span class="mobile-record-value">{{ formatTime(row.check_in_at) }}</span>
                </div>
                <div class="mobile-record-row">
                  <span class="mobile-record-label">Check out</span>
                  <span class="mobile-record-value">{{ formatTime(row.check_out_at) }}</span>
                </div>
                <div class="mobile-record-row">
                  <span class="mobile-record-label">Work hours</span>
                  <span class="mobile-record-value">{{ formatWorkedHours(row.worked_minutes) }}</span>
                </div>
                <div class="mobile-record-row">
                  <span class="mobile-record-label">Extra hours</span>
                  <span class="mobile-record-value">{{ formatWorkedHours(row.extra_minutes) }}</span>
                </div>
                <StatusBadge :label="rowStatusLabel(row)" :tone="statusTone(rowStatusLabel(row))" />
              </article>
            </div>
            <EmptyState
              v-else
              title="No attendance this month"
              body="Your daily attendance will appear here."
            />
          </section>
        </div>

        <form v-if="correctionOpen" class="correction-form" @submit.prevent="submitCorrection">
          <h3 class="m-0">Request correction</h3>
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
      </template>

      <!-- HR: today roster + exception register + review panel -->
      <template v-else>
        <section class="week-block mb-5" aria-labelledby="roster-heading">
          <div class="section-title">
            <Clock3Icon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
            <h2 id="roster-heading" class="mt-0 mb-0">Today</h2>
          </div>
          <p v-if="data?.today" class="today-date">{{ formatDate(data.today) }}</p>
          <Table v-if="data?.roster?.length">
            <TableCaption class="sr-only">Today roster</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Person</TableHead>
                <TableHead>Check in</TableHead>
                <TableHead>Check out</TableHead>
                <TableHead>Work hours</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="row in data.roster" :key="row.employee_id">
                <TableCell>
                  <RouterLink class="text-[#017E84] underline" :to="`/employees/${row.employee_id}`">
                    {{ personLabel(row.employee_name) }}
                  </RouterLink>
                </TableCell>
                <TableCell>{{ formatTime(row.check_in_at) }}</TableCell>
                <TableCell>{{ formatTime(row.check_out_at) }}</TableCell>
                <TableCell class="tabular-nums">{{ formatWorkedHours(row.worked_minutes) }}</TableCell>
                <TableCell>
                  <StatusBadge
                    :label="attendanceStatusLabel(row.status)"
                    :tone="statusTone(attendanceStatusLabel(row.status))"
                  />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <EmptyState v-else title="No roster" body="Active employees for today appear here." />
        </section>
        <div v-if="!controlActionsReady" class="mb-3 flex flex-wrap gap-3">
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

        <div class="hr-summary" aria-label="Exception counts from loaded rows">
          <div class="hr-summary-item">
            <CircleAlertIcon class="size-4" :stroke-width="2" aria-hidden="true" />
            <div>
              <p class="hr-summary-label">Exceptions</p>
              <p class="hr-summary-value">{{ exceptionCount }}</p>
            </div>
          </div>
          <div class="hr-summary-item">
            <Clock3Icon class="size-4" :stroke-width="2" aria-hidden="true" />
            <div>
              <p class="hr-summary-label">Pending corrections</p>
              <p class="hr-summary-value">{{ pendingCorrectionCount }}</p>
            </div>
          </div>
          <div class="hr-summary-item">
            <CircleAlertIcon class="size-4" :stroke-width="2" aria-hidden="true" />
            <div>
              <p class="hr-summary-label">Missing check-outs</p>
              <p class="hr-summary-value">{{ missingCheckOutCount }}</p>
            </div>
          </div>
        </div>

        <EmptyState
          v-if="!data?.exceptions.length"
          title="No exceptions"
          body="Missing check-outs and corrections appear here for review."
        />
        <EmptyState
          v-else-if="visibleExceptions.length === 0"
          title="No results"
          body="No exceptions match this filter."
        >
          <Button type="button" variant="outline" class="mt-3" @click="clearExceptionFilters">
            Clear filters
          </Button>
        </EmptyState>

        <div v-else class="hr-desk">
          <div class="hr-register">
            <h2 class="mt-0 mb-3">Exception register</h2>
            <Table>
              <TableCaption class="sr-only">Attendance exceptions</TableCaption>
              <TableHeader class="sticky top-0 bg-white">
                <TableRow>
                  <TableHead>Exception</TableHead>
                  <TableHead>Person</TableHead>
                  <TableHead>Work date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead class="text-right">Review</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow
                  v-for="row in visibleExceptions"
                  :key="row.id"
                  class="cursor-pointer"
                  :data-selected="selectedException?.id === row.id"
                  @click="selectException(row)"
                >
                  <TableCell>{{ exceptionKindLabel(row.kind) }}</TableCell>
                  <TableCell>
                    <RouterLink
                      v-if="row.employee_id"
                      class="text-[#017E84] underline"
                      :to="`/employees/${row.employee_id}`"
                      @click.stop
                    >
                      {{ personLabel(row.employee_name) }}
                    </RouterLink>
                    <span v-else>{{ personLabel(row.employee_name) }}</span>
                  </TableCell>
                  <TableCell>{{ formatDate(row.work_date) }}</TableCell>
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
                      @click.stop="selectException(row)"
                    >
                      {{ selectedException?.id === row.id ? 'Selected' : 'Review' }}
                    </Button>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </div>

          <section
            v-if="selectedException"
            class="hr-review"
            aria-labelledby="attendance-review-title"
          >
            <p class="eyebrow mb-1">Selected exception</p>
            <h2 id="attendance-review-title" class="mt-0">
              {{ exceptionKindLabel(selectedException.kind) }}
            </h2>
            <dl class="review-details">
              <div>
                <dt>Person</dt>
                <dd>{{ personLabel(selectedException.employee_name) }}</dd>
              </div>
              <div>
                <dt>Work date</dt>
                <dd>{{ formatDate(selectedException.work_date) }}</dd>
              </div>
              <div>
                <dt>Current check in</dt>
                <dd>{{ formatDateTime(selectedException.current_check_in_at) }}</dd>
              </div>
              <div>
                <dt>Current check out</dt>
                <dd>{{ formatDateTime(selectedException.current_check_out_at) }}</dd>
              </div>
              <template v-if="selectedException.kind === 'correction_pending'">
                <div>
                  <dt>Proposed check in</dt>
                  <dd>{{ formatDateTime(selectedException.proposed_check_in_at) }}</dd>
                </div>
                <div>
                  <dt>Proposed check out</dt>
                  <dd>{{ formatDateTime(selectedException.proposed_check_out_at) }}</dd>
                </div>
              </template>
            </dl>
            <p v-if="selectedException.reason" class="mt-3 mb-0 text-sm">
              <strong>Reason:</strong> {{ selectedException.reason }}
            </p>

            <div v-if="selectedException.kind === 'correction_pending'" class="mt-4 grid gap-3">
              <label class="grid gap-1 text-sm font-medium">
                Review comment <span class="font-normal text-muted-foreground">(required to reject)</span>
                <Textarea
                  v-model="reviewComment"
                  rows="3"
                  maxlength="500"
                  placeholder="Add decision context for the audit trail"
                />
              </label>
              <div class="flex flex-wrap gap-2">
                <Button type="button" :disabled="reviewing" @click="reviewCorrection('APPROVED')">
                  Approve correction
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  :disabled="reviewing"
                  @click="reviewCorrection('REJECTED')"
                >
                  Reject correction
                </Button>
              </div>
            </div>
            <p v-else class="missing-note">
              Ask the employee to submit a correction request. Historical punches change only after HR
              reviews that request.
            </p>
          </section>
        </div>
      </template>
    </div>
  </section>
</template>

<style scoped>
.attendance-sheet {
  max-width: 1400px;
}

.attendance-body {
  display: grid;
  gap: 1rem;
}

.employee-layout {
  display: grid;
  gap: 1.5rem;
}

@media (min-width: 900px) {
  .employee-layout {
    grid-template-columns: minmax(16rem, 0.85fr) minmax(0, 1.6fr);
    gap: 0;
    align-items: start;
  }

  .today-block {
    padding-right: 2rem;
  }

  .week-block {
    border-left: 1px solid #dee2e6;
    padding-left: 2rem;
  }
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.section-title h2,
.hr-register h2,
.hr-review h2 {
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
}

.section-icon {
  width: 1.25rem;
  height: 1.25rem;
  flex: none;
  color: #495057;
}

.today-heading-row,
.week-heading-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.today-date {
  margin: 0 0 1rem;
  color: #495057;
  font-size: 14px;
}

.today-details {
  margin: 0;
  border-top: 1px solid #dee2e6;
  padding-top: 0.85rem;
  display: grid;
  gap: 0.65rem;
}

.today-details > div {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  font-size: 14px;
}

.today-details dt {
  margin: 0;
  color: #495057;
}

.today-details dd {
  margin: 0;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.correction-form {
  display: grid;
  gap: 0.75rem;
  max-width: 36rem;
  margin-top: 0.5rem;
  padding-top: 1.25rem;
  border-top: 1px solid #dee2e6;
}

.hr-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.5rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid #dee2e6;
  margin-bottom: 0.25rem;
}

.hr-summary-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  min-width: 8rem;
  color: #495057;
}

.hr-summary-label {
  margin: 0;
  font-size: 13px;
  color: #495057;
}

.hr-summary-value {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #212529;
  font-variant-numeric: tabular-nums;
  line-height: 1.3;
}

.hr-desk {
  display: grid;
  gap: 1.5rem;
}

@media (min-width: 1024px) {
  .hr-desk {
    grid-template-columns: minmax(0, 1.35fr) minmax(18rem, 0.85fr);
    gap: 1.5rem;
    align-items: start;
  }

  .hr-review {
    border-left: 1px solid #dee2e6;
    padding-left: 1.5rem;
  }
}

.hr-review {
  min-width: 0;
}

.eyebrow {
  margin: 0;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  color: #495057;
}

.review-details {
  margin: 0;
  display: grid;
  gap: 0.65rem;
}

@media (min-width: 480px) {
  .review-details {
    grid-template-columns: 1fr 1fr;
  }
}

.review-details dt {
  margin: 0;
  font-size: 13px;
  color: #495057;
}

.review-details dd {
  margin: 0.1rem 0 0;
  font-size: 14px;
  font-weight: 500;
}

.missing-note {
  margin: 1rem 0 0;
  border-left: 4px solid #ffac00;
  background: #fff8dc;
  padding: 0.75rem;
  font-size: 14px;
}

:deep(tr[data-selected='true']) {
  background: #f3eef2;
}
</style>
