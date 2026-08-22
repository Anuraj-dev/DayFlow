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
import type { AttendanceHome } from '@/types/domain'

const session = useSessionStore()
const data = ref<AttendanceHome | null>(null)
const error = ref('')
const actionError = ref('')
const loading = ref(true)

const todayLabel = computed(() => {
  if (data.value?.open_session) return 'Checked in'
  if (data.value?.sessions.some((row) => row.check_out_at)) return 'Checked out'
  return attendanceStatusLabel('not_checked_in')
})

onMounted(async () => {
  try {
    data.value = await api('/api/attendance')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load attendance.'
  } finally {
    loading.value = false
  }
})

async function punch(path: '/api/attendance/check-in' | '/api/attendance/check-out') {
  actionError.value = ''
  try {
    await api(path, { method: 'POST' })
    data.value = await api('/api/attendance')
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Attendance action failed.'
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
    <p v-if="loading">Loading attendance…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <div v-else>
      <div v-if="!session.isHr" class="mb-4">
        <h2 class="mt-0">Today</h2>
        <StatusBadge :label="todayLabel" :tone="statusTone(todayLabel)" />
        <p v-if="actionError" role="alert">{{ actionError }}</p>
        <div class="mt-3 flex gap-2">
          <Button type="button" :disabled="Boolean(data?.open_session)" @click="punch('/api/attendance/check-in')">
            Check in
          </Button>
          <Button
            type="button"
            variant="outline"
            :disabled="!data?.open_session"
            @click="punch('/api/attendance/check-out')"
          >
            Check out
          </Button>
        </div>
      </div>
      <Table v-if="session.isHr">
        <TableCaption class="sr-only">Attendance exceptions</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Exception</TableHead>
            <TableHead>Person</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="!data?.exceptions.length">
            <TableCell colspan="3">Exception queue is empty on the seeded demo.</TableCell>
          </TableRow>
          <TableRow v-for="row in data?.exceptions ?? []" :key="row.id">
            <TableCell>{{ row.kind }}</TableCell>
            <TableCell>{{ row.employee_name ?? row.employee_id }}</TableCell>
            <TableCell>
              <StatusBadge :label="row.status" :tone="statusTone(row.status)" />
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <Table v-else>
        <TableCaption class="sr-only">Attendance sessions</TableCaption>
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
              <StatusBadge
                :label="attendanceStatusLabel(row.status)"
                :tone="statusTone(attendanceStatusLabel(row.status))"
              />
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <EmptyState
        v-if="session.isHr && !data?.exceptions.length"
        title="No exceptions"
        body="Missing check-outs and corrections appear here for review."
      />
    </div>
  </section>
</template>
