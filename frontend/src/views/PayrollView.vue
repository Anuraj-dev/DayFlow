<script setup lang="ts">
import { onMounted, ref } from 'vue'

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
import { statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type { PayrollHome } from '@/types/domain'

const session = useSessionStore()
const data = ref<PayrollHome | null>(null)
const error = ref('')
const actionError = ref('')
const loading = ref(true)

onMounted(async () => {
  try {
    data.value = await api('/api/payroll')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load payroll.'
  } finally {
    loading.value = false
  }
})

async function mutate(path: string) {
  actionError.value = ''
  try {
    await api(path, { method: 'POST' })
    data.value = await api('/api/payroll')
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Payroll action failed.'
  }
}
</script>

<template>
  <section class="sheet">
    <PageHeader
      :title="session.isHr ? 'Payroll control' : 'Payroll'"
      :description="
        session.isHr
          ? 'Draft, finalize, then publish. Finalized records are immutable.'
          : 'Only published payslips for this employee.'
      "
    />
    <p v-if="loading">Loading payroll…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <div v-else-if="data">
      <p v-if="actionError" role="alert">{{ actionError }}</p>
      <Table>
        <TableCaption class="sr-only">Payroll periods</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Period</TableHead>
            <TableHead>Pay date</TableHead>
            <TableHead>Status</TableHead>
            <TableHead v-if="session.isHr">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="!data.periods.length">
            <TableCell :colspan="session.isHr ? 4 : 3">No payroll period.</TableCell>
          </TableRow>
          <TableRow v-for="period in data.periods" :key="period.id">
            <TableCell>{{ period.starts_on }} – {{ period.ends_on }}</TableCell>
            <TableCell>{{ period.pay_date }}</TableCell>
            <TableCell>
              <StatusBadge :label="period.status" :tone="statusTone(period.status)" />
            </TableCell>
            <TableCell v-if="session.isHr" class="flex gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                :disabled="period.status !== 'DRAFT'"
                @click="mutate(`/api/payroll/${period.id}/finalize`)"
              >
                Finalize
              </Button>
              <Button
                type="button"
                size="sm"
                :disabled="period.status !== 'FINALIZED'"
                @click="mutate(`/api/payroll/${period.id}/publish`)"
              >
                Publish
              </Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <p v-if="data.records.length" class="mt-4">
        Net {{ data.records[0]?.currency }} {{ data.records[0]?.net_amount }}
      </p>
      <p v-else class="mt-4 text-[#495057]">No published payslip.</p>
    </div>
  </section>
</template>
