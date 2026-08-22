<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

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
import { formatCurrency, formatDate } from '@/lib/format'
import { payrollStatusLabel, statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type { EmployeeSummary, PayrollHome, PayrollPeriod, PayrollRecord } from '@/types/domain'

const session = useSessionStore()
const data = ref<PayrollHome | null>(null)
const people = ref<EmployeeSummary[]>([])
const error = ref('')
const actionError = ref('')
const actionStatus = ref('')
const loading = ref(true)
const selectedPeriodId = ref('')
const pendingAction = ref<'finalize' | 'publish' | ''>('')
const periodPage = ref(1)
const PERIOD_PAGE_SIZE = 10

function isPublished(status: string | null | undefined): boolean {
  return (status ?? '').toUpperCase() === 'PUBLISHED'
}

function personName(employeeId?: string, fallback?: string | null): string {
  if (fallback) return fallback
  const row = people.value.find((item) => item.id === employeeId)
  if (row) return `${row.first_name} ${row.last_name}`
  return 'Employee'
}

function recordsForPeriod(period: PayrollPeriod, records: PayrollRecord[]): PayrollRecord[] {
  const keyed = records.filter((row) => row.payroll_period_id)
  if (keyed.length) return records.filter((row) => row.payroll_period_id === period.id)
  return records
}

const publishedPeriods = computed(() => {
  const rows = [...(data.value?.periods ?? [])].sort((a, b) => b.ends_on.localeCompare(a.ends_on))
  if (session.isHr) return rows
  return rows.filter((row) => isPublished(row.status))
})

const visibleRecords = computed(() => {
  const rows = data.value?.records ?? []
  if (session.isHr) return rows
  return rows.filter((row) => Boolean(row.published_at))
})

const currentPeriod = computed(() => publishedPeriods.value[0] ?? null)
const priorPeriods = computed(() => publishedPeriods.value.slice(1))

const currentRecord = computed(() => {
  if (!currentPeriod.value) return visibleRecords.value[0] ?? null
  return recordsForPeriod(currentPeriod.value, visibleRecords.value)[0] ?? null
})

const selectedPeriod = computed(() => {
  const rows = data.value?.periods ?? []
  return rows.find((row) => row.id === selectedPeriodId.value) ?? rows[0] ?? null
})

const periodPageCount = computed(() => Math.max(1, Math.ceil(publishedPeriods.value.length / PERIOD_PAGE_SIZE)))
const pagedPeriods = computed(() => {
  const start = (periodPage.value - 1) * PERIOD_PAGE_SIZE
  return publishedPeriods.value.slice(start, start + PERIOD_PAGE_SIZE)
})

const selectedRecords = computed(() => {
  if (!selectedPeriod.value) return []
  return recordsForPeriod(selectedPeriod.value, visibleRecords.value)
})

const salaryRows = computed(() => data.value?.salary_inputs ?? [])

function periodBadge(period: PayrollPeriod): string {
  if (period.validation_errors?.length) return payrollStatusLabel('validation_errors')
  if (period.correction_needed) return payrollStatusLabel('correction_needed')
  return payrollStatusLabel(period.status)
}

function recordFor(period: PayrollPeriod): PayrollRecord | undefined {
  return recordsForPeriod(period, visibleRecords.value)[0]
}

function choosePeriod(home: PayrollHome) {
  const draft = home.periods.find((row) => row.status.toUpperCase() === 'DRAFT')
  selectedPeriodId.value = draft?.id ?? home.periods[0]?.id ?? ''
}

async function loadHome() {
  const home = await api<PayrollHome>('/api/payroll')
  data.value = home
  if (session.isHr) {
    people.value = await api<EmployeeSummary[]>('/api/employees').catch(() => [])
  }
  if (!selectedPeriodId.value || !home.periods.some((row) => row.id === selectedPeriodId.value)) {
    choosePeriod(home)
  }
}

onMounted(async () => {
  try {
    await loadHome()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load payroll.'
  } finally {
    loading.value = false
  }
})

async function mutatePeriod(periodId: string, action: 'finalize' | 'publish') {
  actionError.value = ''
  actionStatus.value = ''
  try {
    await api(`/api/payroll/periods/${periodId}/${action}`, { method: 'POST' })
    pendingAction.value = ''
    await loadHome()
    actionStatus.value = action === 'finalize' ? 'Payroll period finalized.' : 'Payslips published.'
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Payroll action failed.'
  }
}

function requestPeriodAction(action: 'finalize' | 'publish') {
  if (!selectedPeriod.value) return
  if (pendingAction.value === action) {
    void mutatePeriod(selectedPeriod.value.id, action)
    return
  }
  pendingAction.value = action
}

async function downloadPayslip(recordId: string) {
  actionError.value = ''
  actionStatus.value = ''
  try {
    await api(`/api/payroll/records/${recordId}/payslip`)
    actionStatus.value = 'Payslip download prepared.'
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not download payslip.'
  }
}

watch(selectedPeriodId, () => {
  pendingAction.value = ''
})
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
      <p v-if="actionError" class="feedback-error" role="alert">{{ actionError }}</p>
      <p v-if="actionStatus" class="feedback-success" role="status">{{ actionStatus }}</p>

      <template v-if="session.isHr">
        <div class="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm text-[#495057]">
          <p class="m-0">{{ data.periods.length }} payroll periods</p>
          <div class="flex gap-2">
            <Button type="button" size="sm" variant="outline" :disabled="periodPage === 1" @click="periodPage--">Previous</Button>
            <Button type="button" size="sm" variant="outline" :disabled="periodPage === periodPageCount" @click="periodPage++">Next</Button>
          </div>
        </div>
        <Table>
          <TableCaption class="sr-only">Payroll periods</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Period</TableHead>
              <TableHead>Pay date</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Review</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="!data.periods.length">
              <TableCell colspan="4">No payroll period.</TableCell>
            </TableRow>
            <TableRow v-for="period in pagedPeriods" :key="period.id" :data-selected="selectedPeriodId === period.id">
              <TableCell>{{ formatDate(period.starts_on) }} to {{ formatDate(period.ends_on) }}</TableCell>
              <TableCell>{{ formatDate(period.pay_date) }}</TableCell>
              <TableCell>
                <StatusBadge :label="periodBadge(period)" :tone="statusTone(periodBadge(period))" />
              </TableCell>
              <TableCell>
                <Button type="button" size="sm" variant="outline" @click="selectedPeriodId = period.id">
                  {{ selectedPeriodId === period.id ? 'Selected' : 'Review' }}
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>

        <section v-if="selectedPeriod" class="mt-5 border-t border-border pt-5" aria-labelledby="period-review-title">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 id="period-review-title" class="m-0">Selected payroll period</h2>
              <p class="mt-1 mb-0 text-[#495057]">
                {{ formatDate(selectedPeriod.starts_on) }} to {{ formatDate(selectedPeriod.ends_on) }}, pay date {{ formatDate(selectedPeriod.pay_date) }}
              </p>
            </div>
            <StatusBadge :label="periodBadge(selectedPeriod)" :tone="statusTone(periodBadge(selectedPeriod))" />
          </div>
          <div v-if="selectedPeriod.validation_errors?.length" class="feedback-error mt-4" role="alert">
            <strong>Resolve before finalizing</strong>
            <ul class="mb-0">
              <li v-for="message in selectedPeriod.validation_errors" :key="message">{{ message }}</li>
            </ul>
          </div>
          <div class="mt-4 flex flex-wrap gap-2">
            <Button
              v-if="selectedPeriod.status.toUpperCase() === 'DRAFT'"
              type="button"
              variant="outline"
              :disabled="Boolean(selectedPeriod.validation_errors?.length)"
              @click="requestPeriodAction('finalize')"
            >
              {{ pendingAction === 'finalize' ? 'Confirm finalize' : 'Finalize period' }}
            </Button>
            <Button
              v-if="selectedPeriod.status.toUpperCase() === 'FINALIZED'"
              type="button"
              @click="requestPeriodAction('publish')"
            >
              {{ pendingAction === 'publish' ? 'Confirm publish' : 'Publish payslips' }}
            </Button>
            <Button v-if="pendingAction" type="button" variant="ghost" @click="pendingAction = ''">Cancel</Button>
          </div>
          <p v-if="pendingAction" class="mt-2 mb-0 text-sm text-[#495057]">
            {{ pendingAction === 'finalize' ? 'Finalization locks this period and its salary inputs.' : 'Publishing makes payslips visible to employees.' }}
          </p>
        </section>

        <div v-if="data.exceptions?.length" class="mt-4">
          <h2 class="mb-2 text-[21px] font-bold">Exceptions</h2>
          <Table>
            <TableCaption class="sr-only">Payroll exceptions</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Employee</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Detail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="row in data.exceptions" :key="`${row.kind}-${row.employee_id}-${row.detail}`">
                <TableCell>{{ personName(row.employee_id, row.employee_name) }}</TableCell>
                <TableCell>
                  <StatusBadge
                    :label="payrollStatusLabel(row.kind)"
                    :tone="statusTone(payrollStatusLabel(row.kind))"
                  />
                </TableCell>
                <TableCell>{{ row.detail }}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <div class="mt-6">
          <h2 class="mb-2 text-[21px] font-bold">Records</h2>
          <Table>
            <TableCaption class="sr-only">Payroll records</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Employee</TableHead>
                <TableHead>Net</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="!selectedRecords.length">
                <TableCell colspan="3">No payroll records.</TableCell>
              </TableRow>
              <TableRow v-for="row in selectedRecords" :key="row.id">
                <TableCell>{{ personName(row.employee_id, row.employee_name) }}</TableCell>
                <TableCell>{{ formatCurrency(row.currency, row.net_amount) }}</TableCell>
                <TableCell>
                  <StatusBadge
                    :label="row.published_at ? 'Published' : 'Draft'"
                    :tone="statusTone(row.published_at ? 'Published' : 'Draft')"
                  />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <div class="mt-6">
          <h2 class="mb-2 text-[21px] font-bold">Salary structure</h2>
          <p class="m-0 text-[#495057]">
            Configure monthly wage and rates on the employee Salary tab. Finalization snapshots the
            structure effective on the period end date.
          </p>
          <Table v-if="salaryRows.length" class="mt-3">
            <TableCaption class="sr-only">Current salary structures</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Employee</TableHead>
                <TableHead>Monthly wage</TableHead>
                <TableHead>Net</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="row in salaryRows" :key="row.employee_id">
                <TableCell>{{ personName(row.employee_id, row.employee_name) }}</TableCell>
                <TableCell>{{ formatCurrency('INR', row.monthly_wage) }}</TableCell>
                <TableCell>{{ formatCurrency('INR', row.net_amount) }}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </template>

      <template v-else>
        <EmptyState
          v-if="!currentPeriod || !currentRecord"
          title="No published payslip"
          body="Employees see only their own published payroll records after HR publishes a period."
        />
        <div v-else>
          <h2 class="mb-2 text-[21px] font-bold">Current period</h2>
          <div class="hidden sm:block">
            <Table>
            <TableCaption class="sr-only">Current pay period</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Period</TableHead>
                <TableHead>Pay date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Net</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell>{{ formatDate(currentPeriod.starts_on) }} to {{ formatDate(currentPeriod.ends_on) }}</TableCell>
                <TableCell>{{ formatDate(currentPeriod.pay_date) }}</TableCell>
                <TableCell>
                  <StatusBadge
                    :label="periodBadge(currentPeriod)"
                    :tone="statusTone(periodBadge(currentPeriod))"
                  />
                </TableCell>
                <TableCell>{{ formatCurrency(currentRecord.currency, currentRecord.net_amount) }}</TableCell>
                <TableCell>
                  <Button type="button" size="sm" @click="downloadPayslip(currentRecord.id)">
                    Download payslip
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
            </Table>
          </div>
          <article class="mobile-record-list">
            <div class="mobile-record">
              <div class="mobile-record-row">
                <span class="mobile-record-label">Period</span>
                <strong class="mobile-record-value">{{ formatDate(currentPeriod.starts_on) }} to {{ formatDate(currentPeriod.ends_on) }}</strong>
              </div>
              <div class="mobile-record-row">
                <span class="mobile-record-label">Net pay</span>
                <strong class="mobile-record-value">{{ formatCurrency(currentRecord.currency, currentRecord.net_amount) }}</strong>
              </div>
              <StatusBadge :label="periodBadge(currentPeriod)" :tone="statusTone(periodBadge(currentPeriod))" />
              <Button type="button" @click="downloadPayslip(currentRecord.id)">Download payslip</Button>
            </div>
          </article>
          <Table v-if="currentRecord.lines?.length" class="mt-4">
            <TableCaption class="sr-only">Payslip lines</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Component</TableHead>
                <TableHead>Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="line in currentRecord.lines" :key="line.code">
                <TableCell>{{ line.label }}</TableCell>
                <TableCell>{{ formatCurrency(currentRecord.currency, line.amount) }}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <div v-if="priorPeriods.length" class="mt-6">
          <h2 class="mb-2 text-[21px] font-bold">Prior periods</h2>
          <div class="hidden sm:block">
            <Table>
            <TableCaption class="sr-only">Prior pay periods</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Period</TableHead>
                <TableHead>Pay date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Net</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-for="period in priorPeriods" :key="period.id">
                <TableCell>{{ formatDate(period.starts_on) }} to {{ formatDate(period.ends_on) }}</TableCell>
                <TableCell>{{ formatDate(period.pay_date) }}</TableCell>
                <TableCell>
                  <StatusBadge :label="periodBadge(period)" :tone="statusTone(periodBadge(period))" />
                </TableCell>
                <TableCell>
                  <template v-if="recordFor(period)">
                    {{ formatCurrency(recordFor(period)?.currency ?? 'INR', recordFor(period)?.net_amount) }}
                  </template>
                  <template v-else>—</template>
                </TableCell>
              </TableRow>
            </TableBody>
            </Table>
          </div>
          <div class="mobile-record-list">
            <article v-for="period in priorPeriods" :key="period.id" class="mobile-record">
              <div class="mobile-record-row">
                <strong>{{ formatDate(period.starts_on) }} to {{ formatDate(period.ends_on) }}</strong>
                <StatusBadge :label="periodBadge(period)" :tone="statusTone(periodBadge(period))" />
              </div>
              <p class="m-0 text-[#495057]">Paid {{ formatDate(period.pay_date) }}</p>
              <strong v-if="recordFor(period)">{{ formatCurrency(recordFor(period)?.currency ?? 'INR', recordFor(period)?.net_amount) }}</strong>
            </article>
          </div>
        </div>
      </template>
    </div>
  </section>
</template>
