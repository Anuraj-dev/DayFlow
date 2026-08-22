<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

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
import { api, HttpError } from '@/api/client'
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
const loading = ref(true)
const savingSalary = ref(false)
const selectedPeriodId = ref('')
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
    salaryDrafts[row.employee_id] = Object.fromEntries(row.components.map((item) => [item.code, item.amount]))
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
  try {
    await api(`/api/payroll/periods/${periodId}/${action}`, { method: 'POST' })
    await loadHome()
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Payroll action failed.'
  }
}

async function saveSalary() {
  if (!selectedPeriod.value || !salaryEditable.value) return
  actionError.value = ''
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
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not save salary.'
  } finally {
    savingSalary.value = false
  }
}

async function downloadPayslip(recordId: string) {
  actionError.value = ''
  try {
    await api(`/api/payroll/records/${recordId}/payslip`)
  } catch (err) {
    actionError.value = err instanceof HttpError ? err.detail : 'Could not download payslip.'
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

      <template v-if="session.isHr">
        <Table>
          <TableCaption class="sr-only">Payroll periods</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Period</TableHead>
              <TableHead>Pay date</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-if="!data.periods.length">
              <TableCell colspan="4">No payroll period.</TableCell>
            </TableRow>
            <TableRow v-for="period in data.periods" :key="period.id">
              <TableCell>{{ period.starts_on }} – {{ period.ends_on }}</TableCell>
              <TableCell>{{ period.pay_date }}</TableCell>
              <TableCell>
                <StatusBadge :label="periodBadge(period)" :tone="statusTone(periodBadge(period))" />
              </TableCell>
              <TableCell class="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  :disabled="period.status.toUpperCase() !== 'DRAFT'"
                  @click="mutatePeriod(period.id, 'finalize')"
                >
                  Finalize
                </Button>
                <Button
                  type="button"
                  size="sm"
                  :disabled="period.status.toUpperCase() !== 'FINALIZED'"
                  @click="mutatePeriod(period.id, 'publish')"
                >
                  Publish
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>

        <div v-if="data.periods.some((row) => row.validation_errors?.length)" class="mt-4">
          <h2 class="mb-2 text-[21px] font-bold">Validation errors</h2>
          <ul>
            <li v-for="message in data.periods.flatMap((row) => row.validation_errors ?? [])" :key="message">
              {{ message }}
            </li>
          </ul>
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
              <TableRow v-if="!visibleRecords.length">
                <TableCell colspan="3">No payroll records.</TableCell>
              </TableRow>
              <TableRow v-for="row in visibleRecords" :key="row.id">
                <TableCell>{{ personName(row.employee_id, row.employee_name) }}</TableCell>
                <TableCell>{{ row.currency }} {{ row.net_amount }}</TableCell>
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

        <form class="mt-6 grid max-w-lg gap-3" @submit.prevent="saveSalary">
          <h2 class="m-0 text-[21px] font-bold">Salary inputs</h2>
          <p class="m-0 text-[#495057]">
            {{
              salaryEditable
                ? 'Edit salary components before the period is finalized.'
                : 'Salary is locked after finalization. A correction needs a new adjustment period.'
            }}
          </p>
          <div v-for="row in salaryRows" :key="row.employee_id" class="grid gap-3">
            <h3 class="m-0 text-[18px] font-medium">{{ personName(row.employee_id, row.employee_name) }}</h3>
            <label
              v-for="component in row.components"
              :key="`${row.employee_id}-${component.code}`"
              class="grid gap-1 text-sm font-medium"
            >
              {{ component.code }}
              <Input
                :model-value="salaryAmount(row.employee_id, component.code)"
                inputmode="decimal"
                :disabled="!salaryEditable"
                @update:model-value="setSalaryAmount(row.employee_id, component.code, $event)"
              />
            </label>
          </div>
          <Button type="submit" :disabled="!salaryEditable || savingSalary || !salaryRows.length">
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
          <h2 class="mb-2 text-[21px] font-bold">Current period</h2>
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
                <TableCell>{{ currentPeriod.starts_on }} – {{ currentPeriod.ends_on }}</TableCell>
                <TableCell>{{ currentPeriod.pay_date }}</TableCell>
                <TableCell>
                  <StatusBadge
                    :label="periodBadge(currentPeriod)"
                    :tone="statusTone(periodBadge(currentPeriod))"
                  />
                </TableCell>
                <TableCell>{{ currentRecord.currency }} {{ currentRecord.net_amount }}</TableCell>
                <TableCell>
                  <Button type="button" size="sm" @click="downloadPayslip(currentRecord.id)">
                    Download payslip
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
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
                <TableCell>{{ currentRecord.currency }} {{ line.amount }}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <div v-if="priorPeriods.length" class="mt-6">
          <h2 class="mb-2 text-[21px] font-bold">Prior periods</h2>
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
                <TableCell>{{ period.starts_on }} – {{ period.ends_on }}</TableCell>
                <TableCell>{{ period.pay_date }}</TableCell>
                <TableCell>
                  <StatusBadge :label="periodBadge(period)" :tone="statusTone(periodBadge(period))" />
                </TableCell>
                <TableCell>
                  <template v-if="recordFor(period)">
                    {{ recordFor(period)?.currency }} {{ recordFor(period)?.net_amount }}
                  </template>
                  <template v-else>—</template>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </template>
    </div>
  </section>
</template>
