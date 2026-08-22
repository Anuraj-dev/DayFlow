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
import { attendanceStatusLabel, exceptionKindLabel, statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type { AttendanceException, AttendanceHome, AttendanceSession } from '@/types/domain'

const session = useSessionStore()
const data = ref<AttendanceHome | null>(null)
const error = ref('')
const actionError = ref('')
const loading = ref(true)

const kindFilter = ref<'all' | 'missing_check_out' | 'correction_pending'>('all')
const personFilter = ref('')
const correctionOpen = ref(false)
const correctionSessionId = ref('')
const proposedCheckIn = ref('')
const proposedCheckOut = ref('')
const correctionReason = ref('')
const pendingCorrections = ref<Set<string>>(new Set())

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

onMounted(async () => {
  try {
    const home = await api<AttendanceHome>('/api/attendance')
    data.value = home
    if (!correctionSessionId.value) {
      correctionSessionId.value = home.sessions[0]?.id ?? ''
    }
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
  try {
    await api(path, { method: 'POST' })
    data.value = await api('/api/attendance')
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Attendance action failed.'
  }
}

function openCorrection(sessionId?: string) {
  actionError.value = ''
  correctionOpen.value = true
  correctionSessionId.value = sessionId || data.value?.sessions[0]?.id || ''
  const row = data.value?.sessions.find((item) => item.id === correctionSessionId.value)
  proposedCheckIn.value = row?.check_in_at ?? ''
  proposedCheckOut.value = row?.check_out_at ?? ''
}

async function submitCorrection() {
  actionError.value = ''
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
        proposed_check_in_at: proposedCheckIn.value,
        proposed_check_out_at: proposedCheckOut.value || null,
        reason,
      }),
    })
    pendingCorrections.value = new Set([...pendingCorrections.value, correctionSessionId.value])
    correctionOpen.value = false
    correctionReason.value = ''
    data.value = await api('/api/attendance')
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not request a correction.'
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
      <p v-if="actionError" role="alert">{{ actionError }}</p>
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
            <Input v-model="proposedCheckIn" type="text" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Proposed check out
            <Input v-model="proposedCheckOut" type="text" />
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
      />
      <Table v-else-if="session.isHr">
        <TableCaption class="sr-only">Attendance exceptions</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Exception</TableHead>
            <TableHead>Person</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="row in visibleExceptions" :key="row.id">
            <TableCell>{{ exceptionKindLabel(row.kind) }}</TableCell>
            <TableCell>{{ row.employee_name ?? row.employee_id }}</TableCell>
            <TableCell>
              <StatusBadge
                :label="exceptionStatusLabel(row)"
                :tone="statusTone(exceptionStatusLabel(row))"
              />
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <template v-else>
        <h2>This week</h2>
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
              <TableCell>{{ row.work_date ?? '—' }}</TableCell>
              <TableCell>{{ row.check_in_at ?? '—' }}</TableCell>
              <TableCell>{{ row.check_out_at ?? '—' }}</TableCell>
              <TableCell>
                <StatusBadge :label="sessionLabel(row)" :tone="statusTone(sessionLabel(row))" />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </template>
    </div>
  </section>
</template>
