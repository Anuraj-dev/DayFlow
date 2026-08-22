<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { BanknoteIcon, CalendarDaysIcon, FileDownIcon, LockKeyholeIcon } from '@lucide/vue'

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
import { api, getToken, HttpError } from '@/api/client'
import { formatCurrency, formatDate, formatEnumLabel } from '@/lib/format'
import { payrollStatusLabel, statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type {
  EmployeeSalaryInputs,
  EmployeeSummary,
  PayrollHome,
  PayrollPeriod,
  PayrollRecord,
} from '@/types/domain'

const session = useSessionStore()
const data = ref<PayrollHome | null>(null)
const people = ref<EmployeeSummary[]>([])
const error = ref('')
const actionError = ref('')
const actionStatus = ref('')
const loading = ref(true)
const savingSalary = ref(false)
const selectedPeriodId = ref('')
const pendingAction = ref<'finalize' | 'publish' | ''>('')
const periodPage = ref(1)
const PERIOD_PAGE_SIZE = 10
const salaryDrafts = reactive<Record<string, Record<string, string>>>({})

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

const periodPageCount = computed(() =>
  Math.max(1, Math.ceil(publishedPeriods.value.length / PERIOD_PAGE_SIZE)),
)
const pagedPeriods = computed(() => {
  const start = (periodPage.value - 1) * PERIOD_PAGE_SIZE
  return publishedPeriods.value.slice(start, start + PERIOD_PAGE_SIZE)
})

const selectedRecords = computed(() => {
  if (!selectedPeriod.value) return []
  return recordsForPeriod(selectedPeriod.value, visibleRecords.value)
})

const salaryEditable = computed(() => selectedPeriod.value?.status.toUpperCase() === 'DRAFT')

const salaryRows = computed(() => data.value?.salary_inputs ?? [])

function periodBadge(period: PayrollPeriod): string {
  if (period.validation_errors?.length) return payrollStatusLabel('validation_errors')
  if (period.correction_needed) return payrollStatusLabel('correction_needed')
  return payrollStatusLabel(period.status)
}

function recordFor(period: PayrollPeriod): PayrollRecord | undefined {
  return recordsForPeriod(period, visibleRecords.value)[0]
}

function initSalaryDrafts(inputs: EmployeeSalaryInputs[]) {
  for (const key of Object.keys(salaryDrafts)) delete salaryDrafts[key]
  for (const row of inputs) {
    salaryDrafts[row.employee_id] = Object.fromEntries(
      row.components.map((item) => [item.code, item.amount]),
    )
  }
}

function choosePeriod(home: PayrollHome) {
  const draft = home.periods.find((row) => row.status.toUpperCase() === 'DRAFT')
  selectedPeriodId.value = draft?.id ?? home.periods[0]?.id ?? ''
}

function salaryAmount(employeeId: string, code: string): string {
  return salaryDrafts[employeeId]?.[code] ?? ''
}

function setSalaryAmount(employeeId: string, code: string, value: string | number) {
  const row = salaryDrafts[employeeId] ?? (salaryDrafts[employeeId] = {})
  row[code] = String(value)
}

async function loadHome() {
  const home = await api<PayrollHome>('/api/payroll')
  data.value = home
  if (session.isHr) {
    people.value = await api<EmployeeSummary[]>('/api/employees').catch(() => [])
  }
  initSalaryDrafts(home.salary_inputs ?? [])
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

async function saveSalary() {
  if (!selectedPeriod.value || !salaryEditable.value) return
  actionError.value = ''
  actionStatus.value = ''
  savingSalary.value = true
  try {
    for (const row of salaryRows.value) {
      const amounts = salaryDrafts[row.employee_id] ?? {}
      await api('/api/payroll/salary-components', {
        method: 'PATCH',
        body: JSON.stringify({
          employee_id: row.employee_id,
          period_id: selectedPeriod.value.id,
          components: row.components.map((item) => ({
            code: item.code,
            amount: amounts[item.code] ?? item.amount,
          })),
        }),
      })
    }
    await loadHome()
    actionStatus.value = 'Salary inputs saved.'
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not save salary.'
  } finally {
    savingSalary.value = false
  }
}

async function downloadPayslip(recordId: string) {
  actionError.value = ''
  actionStatus.value = ''
  try {
    const headers = new Headers({ Accept: 'text/html' })
    const token = getToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const response = await fetch(`/api/payroll/records/${recordId}/payslip`, { headers })
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { detail?: string }
      throw new HttpError(response.status, payload.detail || response.statusText)
    }
    const disposition = response.headers.get('Content-Disposition') ?? ''
    const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? `payslip-${recordId}.html`
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1_000)
    actionStatus.value = 'Payslip downloaded.'
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
        <div class="grid gap-6 lg:grid-cols-[minmax(28rem,0.9fr)_minmax(24rem,1.1fr)] lg:gap-0">
          <section
            class="lg:border-r lg:border-border lg:pr-8"
            aria-labelledby="payroll-periods-title"
          >
            <h2 id="payroll-periods-title" class="mt-0 mb-2">Payroll periods</h2>
            <div
              class="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground"
            >
              <p class="m-0">{{ data.periods.length }} payroll periods</p>
              <div class="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  :disabled="periodPage === 1"
                  @click="periodPage--"
                  >Previous</Button
                >
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  :disabled="periodPage === periodPageCount"
                  @click="periodPage++"
                  >Next</Button
                >
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
                <TableRow
                  v-for="period in pagedPeriods"
                  :key="period.id"
                  :data-selected="selectedPeriodId === period.id"
                >
                  <TableCell
                    >{{ formatDate(period.starts_on) }} to
                    {{ formatDate(period.ends_on) }}</TableCell
                  >
                  <TableCell>{{ formatDate(period.pay_date) }}</TableCell>
                  <TableCell>
                    <StatusBadge
                      :label="periodBadge(period)"
                      :tone="statusTone(periodBadge(period))"
                    />
                  </TableCell>
                  <TableCell>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      @click="selectedPeriodId = period.id"
                    >
                      {{ selectedPeriodId === period.id ? 'Selected' : 'Review' }}
                    </Button>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </section>

          <section v-if="selectedPeriod" class="lg:pl-8" aria-labelledby="period-review-title">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 id="period-review-title" class="m-0">Selected payroll period</h2>
                <p class="mt-1 mb-0 text-[#495057]">
                  {{ formatDate(selectedPeriod.starts_on) }} to
                  {{ formatDate(selectedPeriod.ends_on) }}, pay date
                  {{ formatDate(selectedPeriod.pay_date) }}
                </p>
              </div>
              <StatusBadge
                :label="periodBadge(selectedPeriod)"
                :tone="statusTone(periodBadge(selectedPeriod))"
              />
            </div>
            <div
              v-if="selectedPeriod.validation_errors?.length"
              class="feedback-error mt-4"
              role="alert"
            >
              <strong>Resolve before finalizing</strong>
              <ul class="mb-0">
                <li v-for="message in selectedPeriod.validation_errors" :key="message">
                  {{ message }}
                </li>
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
              <Button v-if="pendingAction" type="button" variant="ghost" @click="pendingAction = ''"
                >Cancel</Button
              >
            </div>
            <p v-if="pendingAction" class="mt-2 mb-0 text-sm text-[#495057]">
              {{
                pendingAction === 'finalize'
                  ? 'Finalization locks this period and its salary inputs.'
                  : 'Publishing makes payslips visible to employees.'
              }}
            </p>
          </section>
        </div>

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
              <TableRow
                v-for="row in data.exceptions"
                :key="`${row.kind}-${row.employee_id}-${row.detail}`"
              >
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

        <form class="mt-6 grid gap-3 border-t border-border pt-5" @submit.prevent="saveSalary">
          <h2 class="m-0 text-[21px] font-bold">Salary inputs</h2>
          <p class="m-0 text-[#495057]">
            {{
              salaryEditable
                ? 'Edit salary components before the period is finalized.'
                : 'Salary is locked after finalization. A correction needs a new adjustment period.'
            }}
          </p>
          <div
            v-for="row in salaryRows"
            :key="row.employee_id"
            class="grid gap-3 border-b border-border pb-4 last:border-0 sm:grid-cols-[minmax(10rem,0.7fr)_minmax(0,2fr)]"
          >
            <h3 class="m-0 text-[18px] font-medium">
              {{ personName(row.employee_id, row.employee_name) }}
            </h3>
            <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <label
                v-for="component in row.components"
                :key="`${row.employee_id}-${component.code}`"
                class="grid gap-1 text-sm font-medium"
              >
                {{ component.name || formatEnumLabel(component.code) }}
                <span class="font-normal text-muted-foreground">{{ component.code }}</span>
                <Input
                  :model-value="salaryAmount(row.employee_id, component.code)"
                  inputmode="decimal"
                  :disabled="!salaryEditable"
                  @update:model-value="setSalaryAmount(row.employee_id, component.code, $event)"
                />
              </label>
            </div>
          </div>
          <Button
            class="w-fit"
            type="submit"
            :disabled="!salaryEditable || savingSalary || !salaryRows.length"
          >
            Save salary
          </Button>
        </form>
      </template>

      <template v-else>
        <EmptyState
          v-if="!currentPeriod || !currentRecord"
          title="No published payslip"
          body="Employees see only their own published payroll records after HR publishes a period."
        />
        <div v-else>
          <div
            class="grid gap-6 border-b border-border pb-6 lg:grid-cols-[minmax(20rem,0.85fr)_minmax(24rem,1.15fr)] lg:gap-0"
          >
            <section
              class="lg:border-r lg:border-border lg:pr-8"
              aria-labelledby="current-pay-period-title"
            >
              <div class="mb-3 flex items-center gap-2">
                <CalendarDaysIcon class="size-5" :stroke-width="1.75" aria-hidden="true" />
                <h2 id="current-pay-period-title" class="m-0">Current period</h2>
              </div>
              <dl class="grid gap-0 text-sm">
                <div class="flex justify-between gap-4 border-b border-border py-2">
                  <dt class="text-muted-foreground">Period</dt>
                  <dd class="m-0 text-right font-medium">
                    {{ formatDate(currentPeriod.starts_on) }} to
                    {{ formatDate(currentPeriod.ends_on) }}
                  </dd>
                </div>
                <div class="flex justify-between gap-4 border-b border-border py-2">
                  <dt class="text-muted-foreground">Pay date</dt>
                  <dd class="m-0 font-medium">{{ formatDate(currentPeriod.pay_date) }}</dd>
                </div>
                <div class="flex items-center justify-between gap-4 border-b border-border py-2">
                  <dt class="text-muted-foreground">Status</dt>
                  <dd class="m-0">
                    <StatusBadge
                      :label="periodBadge(currentPeriod)"
                      :tone="statusTone(periodBadge(currentPeriod))"
                    />
                  </dd>
                </div>
                <div class="flex items-center justify-between gap-4 py-3">
                  <dt class="flex items-center gap-2 font-medium">
                    <BanknoteIcon class="size-4" aria-hidden="true" />Net pay
                  </dt>
                  <dd class="m-0 text-xl font-bold tabular-nums">
                    {{ formatCurrency(currentRecord.currency, currentRecord.net_amount) }}
                  </dd>
                </div>
              </dl>
              <Button class="mt-3" type="button" @click="downloadPayslip(currentRecord.id)">
                <FileDownIcon class="size-4" aria-hidden="true" />
                Download payslip
              </Button>
            </section>
            <section class="lg:pl-8" aria-labelledby="pay-components-title">
              <div class="mb-3 flex items-center gap-2">
                <LockKeyholeIcon class="size-5" :stroke-width="1.75" aria-hidden="true" />
                <h2 id="pay-components-title" class="m-0">Pay components</h2>
              </div>
              <Table v-if="currentRecord.lines?.length">
                <TableCaption class="sr-only">Payslip lines</TableCaption>
                <TableHeader
                  ><TableRow
                    ><TableHead>Component</TableHead
                    ><TableHead class="text-right">Amount</TableHead></TableRow
                  ></TableHeader
                >
                <TableBody>
                  <TableRow v-for="line in currentRecord.lines" :key="line.code">
                    <TableCell>{{ line.label }}</TableCell>
                    <TableCell class="text-right tabular-nums">{{
                      formatCurrency(currentRecord.currency, line.amount)
                    }}</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
              <p v-else class="m-0 text-muted-foreground">No component breakdown is available.</p>
            </section>
          </div>
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
                  <TableCell
                    >{{ formatDate(period.starts_on) }} to
                    {{ formatDate(period.ends_on) }}</TableCell
                  >
                  <TableCell>{{ formatDate(period.pay_date) }}</TableCell>
                  <TableCell>
                    <StatusBadge
                      :label="periodBadge(period)"
                      :tone="statusTone(periodBadge(period))"
                    />
                  </TableCell>
                  <TableCell>
                    <template v-if="recordFor(period)">
                      {{
                        formatCurrency(
                          recordFor(period)?.currency ?? 'INR',
                          recordFor(period)?.net_amount,
                        )
                      }}
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
                <strong
                  >{{ formatDate(period.starts_on) }} to {{ formatDate(period.ends_on) }}</strong
                >
                <StatusBadge :label="periodBadge(period)" :tone="statusTone(periodBadge(period))" />
              </div>
              <p class="m-0 text-[#495057]">Paid {{ formatDate(period.pay_date) }}</p>
              <strong v-if="recordFor(period)">{{
                formatCurrency(recordFor(period)?.currency ?? 'INR', recordFor(period)?.net_amount)
              }}</strong>
            </article>
          </div>
        </div>
      </template>
    </div>
  </section>
</template>
