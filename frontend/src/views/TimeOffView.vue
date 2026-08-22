<script setup lang="ts">
import { onMounted, ref } from 'vue'

import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
import { statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type { TimeOffHome } from '@/types/domain'

const session = useSessionStore()
const data = ref<TimeOffHome | null>(null)
const error = ref('')
const actionError = ref('')
const loading = ref(true)
const leaveType = ref('paid')
const startsOn = ref('')
const endsOn = ref('')
const reason = ref('')
const submitting = ref(false)

onMounted(async () => {
  try {
    data.value = await api('/api/time-off')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load time off.'
  } finally {
    loading.value = false
  }
})

async function submitRequest() {
  actionError.value = ''
  submitting.value = true
  try {
    await api('/api/time-off', {
      method: 'POST',
      body: JSON.stringify({
        leave_type: leaveType.value,
        starts_on: startsOn.value,
        ends_on: endsOn.value,
        reason: reason.value,
      }),
    })
    data.value = await api('/api/time-off')
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not submit leave.'
  } finally {
    submitting.value = false
  }
}

async function decide(id: string, decision: 'approve' | 'reject') {
  actionError.value = ''
  try {
    await api(`/api/time-off/${id}/${decision}`, { method: 'POST', body: JSON.stringify({ comment: reason.value }) })
    data.value = await api('/api/time-off')
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not update leave.'
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

      <div v-if="session.isHr">
        <h2>Pending queue</h2>
        <Table>
          <TableCaption class="sr-only">Pending leave requests</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Employee</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Dates</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="!data?.pending_queue.length">
              <TableCell colspan="5">No pending requests</TableCell>
            </TableRow>
            <TableRow v-for="row in data?.pending_queue ?? []" :key="row.id">
              <TableCell>{{ row.employee_name ?? 'Employee' }}</TableCell>
              <TableCell>{{ row.leave_type }}</TableCell>
              <TableCell>{{ row.starts_on }} – {{ row.ends_on }}</TableCell>
              <TableCell>
                <StatusBadge :label="row.status" :tone="statusTone(row.status)" />
              </TableCell>
              <TableCell class="flex gap-2">
                <Button type="button" size="sm" @click="decide(row.id, 'approve')">Approve</Button>
                <Button type="button" size="sm" variant="outline" @click="decide(row.id, 'reject')">Reject</Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
      <div v-else>
        <h2>Requests</h2>
        <Table>
          <TableCaption class="sr-only">Leave requests</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Type</TableHead>
              <TableHead>Dates</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="!data?.requests.length">
              <TableCell colspan="3">No requests yet</TableCell>
            </TableRow>
            <TableRow v-for="row in data?.requests ?? []" :key="row.id">
              <TableCell>{{ row.leave_type }}</TableCell>
              <TableCell>{{ row.starts_on }} – {{ row.ends_on }}</TableCell>
              <TableCell>
                <StatusBadge :label="row.status" :tone="statusTone(row.status)" />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <form class="mt-4 grid max-w-lg gap-3" @submit.prevent="submitRequest">
          <h3 class="m-0">Submit a request</h3>
          <label class="grid gap-1 text-sm font-medium">
            Leave type
            <Input v-model="leaveType" required />
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
          <Button type="submit" :disabled="submitting">{{ submitting ? 'Submitting…' : 'Submit request' }}</Button>
        </form>
      </div>
      <EmptyState
        v-if="session.isHr && !data?.pending_queue.length"
        title="No pending requests"
        body="Rejection requires a comment. Approval updates balance and attendance in one transaction."
      />
    </div>
  </section>
</template>
