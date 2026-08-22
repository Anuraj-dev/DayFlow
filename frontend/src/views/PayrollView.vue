<script setup lang="ts">
import {
  BanknoteIcon,
  CircleAlertIcon,
  DownloadIcon,
  FileTextIcon,
  LockIcon,
} from '@lucide/vue'
import { computed, nextTick, onMounted, ref, watch } from 'vue'

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
const controlActionsReady = ref(false)

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

const selectedNetTotal = computed(() => {
  if (!selectedRecords.value.length) return null
  const currency = selectedRecords.value[0]?.currency ?? 'INR'
  const total = selectedRecords.value.reduce((sum, row) => sum + Number(row.net_amount), 0)
  if (!Number.isFinite(total)) return null
  return { currency, total: total.toFixed(2) }
})

const salaryRows = computed(() => data.value?.salary_inputs ?? [])

const canFinalize = computed(
  () =>
    selectedPeriod.value?.status.toUpperCase() === 'DRAFT' &&
    !selectedPeriod.value.validation_errors?.length,
)

const canPublish = computed(() => selectedPeriod.value?.status.toUpperCase() === 'FINALIZED')

function periodBadge(period: PayrollPeriod): string {
  if (period.validation_errors?.length) return payrollStatusLabel('validation_errors')
  if (period.correction_needed) return payrollStatusLabel('correction_needed')
  return payrollStatusLabel(period.status)
}

function recordFor(period: PayrollPeriod): PayrollRecord | undefined {
  return recordsForPeriod(period, visibleRecords.value)[0]
}

function periodNet(period: PayrollPeriod): { currency: string; total: string } | null {
  const rows = recordsForPeriod(period, visibleRecords.value)
  if (!rows.length) return null
  const currency = rows[0]?.currency ?? 'INR'
  const total = rows.reduce((sum, row) => sum + Number(row.net_amount), 0)
  if (!Number.isFinite(total)) return null
  return { currency, total: total.toFixed(2) }
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
  await nextTick()
  controlActionsReady.value = Boolean(document.getElementById('control-actions'))
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
  <section class="sheet payroll-sheet">
    <Teleport
      v-if="
        controlActionsReady &&
        !loading &&
        !error &&
        data &&
        ((session.isHr &&
          selectedPeriod &&
          (selectedPeriod.status.toUpperCase() === 'DRAFT' || canPublish || pendingAction)) ||
          (!session.isHr && currentRecord))
      "
      defer
      to="#control-actions"
    >
      <div class="flex flex-wrap items-center gap-2">
        <template v-if="session.isHr && selectedPeriod">
          <Button
            v-if="selectedPeriod.status.toUpperCase() === 'DRAFT'"
            type="button"
            :disabled="!canFinalize"
            @click="requestPeriodAction('finalize')"
          >
            {{ pendingAction === 'finalize' ? 'Confirm finalize' : 'Finalize period' }}
          </Button>
          <Button
            v-if="canPublish"
            type="button"
            @click="requestPeriodAction('publish')"
          >
            {{ pendingAction === 'publish' ? 'Confirm publish' : 'Publish payslips' }}
          </Button>
          <Button v-if="pendingAction" type="button" variant="ghost" @click="pendingAction = ''">
            Cancel
          </Button>
        </template>
        <Button
          v-else-if="currentRecord"
          type="button"
          @click="downloadPayslip(currentRecord.id)"
        >
          <DownloadIcon class="size-4" :stroke-width="1.75" aria-hidden="true" />
          Download payslip
        </Button>
      </div>
    </Teleport>

    <PageHeader
      v-if="session.isHr"
      title="Payroll control"
      description="Draft, finalize, then publish. Finalized records are immutable."
    />
    <p v-if="loading">Loading payroll…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <div v-else-if="data" class="payroll-body">
      <p v-if="actionError" class="feedback-error" role="alert">{{ actionError }}</p>
      <p v-if="actionStatus" class="feedback-success" role="status">{{ actionStatus }}</p>

      <template v-if="session.isHr">
        <section class="payroll-section" aria-labelledby="period-register-title">
          <div class="section-heading">
            <div class="section-title">
              <BanknoteIcon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
              <h2 id="period-register-title">Period register</h2>
            </div>
            <div class="section-meta">
              <span>{{ data.periods.length }} payroll periods</span>
              <div class="flex gap-2">
                <Button type="button" size="sm" variant="outline" :disabled="periodPage === 1" @click="periodPage--">
                  Previous
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  :disabled="periodPage === periodPageCount"
                  @click="periodPage++"
                >
                  Next
                </Button>
              </div>
            </div>
          </div>

          <Table>
            <TableCaption class="sr-only">Payroll periods</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Period</TableHead>
                <TableHead>Pay date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead class="text-right">Net</TableHead>
                <TableHead class="text-right">Review</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="!data.periods.length">
                <TableCell colspan="5">No payroll period.</TableCell>
              </TableRow>
              <TableRow
                v-for="period in pagedPeriods"
                :key="period.id"
                :data-selected="selectedPeriodId === period.id"
                class="cursor-pointer"
                @click="selectedPeriodId = period.id"
              >
                <TableCell>{{ formatDate(period.starts_on) }} to {{ formatDate(period.ends_on) }}</TableCell>
                <TableCell>{{ formatDate(period.pay_date) }}</TableCell>
                <TableCell>
                  <StatusBadge :label="periodBadge(period)" :tone="statusTone(periodBadge(period))" />
                </TableCell>
                <TableCell class="text-right tabular-nums">
                  <template v-if="periodNet(period)">
                    {{ formatCurrency(periodNet(period)!.currency, periodNet(period)!.total) }}
                  </template>
                  <template v-else>—</template>
                </TableCell>
                <TableCell class="text-right">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    @click.stop="selectedPeriodId = period.id"
                  >
                    {{ selectedPeriodId === period.id ? 'Selected' : 'Review' }}
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </section>

        <section
          v-if="selectedPeriod"
          class="payroll-section selected-period"
          aria-labelledby="period-review-title"
        >
          <div class="section-heading">
            <div class="section-title">
              <FileTextIcon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
              <div>
                <h2 id="period-review-title">Selected payroll period</h2>
                <p class="section-subtitle">
                  {{ formatDate(selectedPeriod.starts_on) }} to {{ formatDate(selectedPeriod.ends_on) }},
                  pay date {{ formatDate(selectedPeriod.pay_date) }}
                </p>
              </div>
            </div>
            <StatusBadge
              :label="periodBadge(selectedPeriod)"
              :tone="statusTone(periodBadge(selectedPeriod))"
            />
          </div>

          <dl v-if="selectedNetTotal" class="summary-grid">
            <div>
              <dt>Records</dt>
              <dd>{{ selectedRecords.length }}</dd>
            </div>
            <div>
              <dt>Net total</dt>
              <dd class="tabular-nums">
                {{ formatCurrency(selectedNetTotal.currency, selectedNetTotal.total) }}
              </dd>
            </div>
          </dl>

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
            <Button v-if="pendingAction" type="button" variant="ghost" @click="pendingAction = ''">
              Cancel
            </Button>
          </div>
          <p v-if="pendingAction" class="mt-2 mb-0 text-sm text-[#495057]">
            {{
              pendingAction === 'finalize'
                ? 'Finalization locks this period and its salary inputs.'
                : 'Publishing makes payslips visible to employees.'
            }}
          </p>
        </section>

        <section v-if="data.exceptions?.length" class="payroll-section" aria-labelledby="exceptions-title">
          <div class="section-heading">
            <div class="section-title">
              <CircleAlertIcon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
              <h2 id="exceptions-title">Exceptions</h2>
            </div>
          </div>
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
        </section>

        <section class="payroll-section" aria-labelledby="records-title">
          <div class="section-heading">
            <div class="section-title">
              <BanknoteIcon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
              <h2 id="records-title">Records</h2>
            </div>
          </div>
          <Table>
            <TableCaption class="sr-only">Payroll records</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Employee</TableHead>
                <TableHead class="text-right">Net</TableHead>
                <TableHead>Payable days</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow v-if="!selectedRecords.length">
                <TableCell colspan="4">No payroll records.</TableCell>
              </TableRow>
              <TableRow v-for="row in selectedRecords" :key="row.id">
                <TableCell>{{ personName(row.employee_id, row.employee_name) }}</TableCell>
                <TableCell class="text-right tabular-nums">
                  {{ formatCurrency(row.currency, row.net_amount) }}
                </TableCell>
                <TableCell>{{ row.payable_days ?? '—' }} / {{ row.scheduled_days ?? '—' }}</TableCell>
                <TableCell>
                  <StatusBadge
                    :label="row.published_at ? 'Published' : 'Draft'"
                    :tone="statusTone(row.published_at ? 'Published' : 'Draft')"
                  />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </section>

        <section class="payroll-section" aria-labelledby="salary-title">
          <div class="section-heading">
            <div class="section-title">
              <LockIcon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
              <div>
                <h2 id="salary-title">Salary structure</h2>
                <p class="section-subtitle">
                  Configure monthly wage and rates on the employee Salary tab. Finalization snapshots
                  the structure effective on the period end date.
                </p>
              </div>
            </div>
          </div>
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
          <p v-else class="m-0 text-sm text-[#495057]">No salary inputs for this period.</p>
        </section>
      </template>

      <template v-else>
        <EmptyState
          v-if="!currentPeriod || !currentRecord"
          title="No published payslip"
          body="Employees see only their own published payroll records after HR publishes a period."
        />
        <div v-else class="employee-payroll">
          <section class="payroll-section" aria-labelledby="current-period-title">
            <div class="section-heading">
              <div class="section-title">
                <BanknoteIcon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
                <h2 id="current-period-title">Current period</h2>
              </div>
              <Button type="button" size="sm" @click="downloadPayslip(currentRecord.id)">
                <DownloadIcon class="size-4" :stroke-width="1.75" aria-hidden="true" />
                Download payslip
              </Button>
            </div>

            <dl class="summary-grid">
              <div>
                <dt>Period</dt>
                <dd>
                  {{ formatDate(currentPeriod.starts_on) }} to {{ formatDate(currentPeriod.ends_on) }}
                </dd>
              </div>
              <div>
                <dt>Pay date</dt>
                <dd>{{ formatDate(currentPeriod.pay_date) }}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  <StatusBadge
                    :label="periodBadge(currentPeriod)"
                    :tone="statusTone(periodBadge(currentPeriod))"
                  />
                </dd>
              </div>
              <div>
                <dt>Net pay</dt>
                <dd class="net-amount tabular-nums">
                  {{ formatCurrency(currentRecord.currency, currentRecord.net_amount) }}
                </dd>
              </div>
              <div>
                <dt>Payable days</dt>
                <dd class="tabular-nums">
                  {{ currentRecord.payable_days ?? '—' }} / {{ currentRecord.scheduled_days ?? '—' }}
                </dd>
              </div>
            </dl>

            <div class="hidden sm:block">
              <Table>
                <TableCaption class="sr-only">Current pay period</TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead>Period</TableHead>
                    <TableHead>Pay date</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead class="text-right">Net</TableHead>
                    <TableHead>Payable days</TableHead>
                    <TableHead class="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell>
                      {{ formatDate(currentPeriod.starts_on) }} to {{ formatDate(currentPeriod.ends_on) }}
                    </TableCell>
                    <TableCell>{{ formatDate(currentPeriod.pay_date) }}</TableCell>
                    <TableCell>
                      <StatusBadge
                        :label="periodBadge(currentPeriod)"
                        :tone="statusTone(periodBadge(currentPeriod))"
                      />
                    </TableCell>
                    <TableCell class="text-right tabular-nums">
                      {{ formatCurrency(currentRecord.currency, currentRecord.net_amount) }}
                    </TableCell>
                    <TableCell>
                      {{ currentRecord.payable_days ?? '—' }} / {{ currentRecord.scheduled_days ?? '—' }}
                    </TableCell>
                    <TableCell class="text-right">
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
                  <strong class="mobile-record-value">
                    {{ formatDate(currentPeriod.starts_on) }} to {{ formatDate(currentPeriod.ends_on) }}
                  </strong>
                </div>
                <div class="mobile-record-row">
                  <span class="mobile-record-label">Net pay</span>
                  <strong class="mobile-record-value">
                    {{ formatCurrency(currentRecord.currency, currentRecord.net_amount) }}
                  </strong>
                </div>
                <StatusBadge
                  :label="periodBadge(currentPeriod)"
                  :tone="statusTone(periodBadge(currentPeriod))"
                />
                <Button type="button" @click="downloadPayslip(currentRecord.id)">Download payslip</Button>
              </div>
            </article>
          </section>

          <section
            v-if="currentRecord.lines?.length"
            class="payroll-section"
            aria-labelledby="components-title"
          >
            <div class="section-heading">
              <div class="section-title">
                <FileTextIcon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
                <h2 id="components-title">Components</h2>
              </div>
            </div>
            <Table>
              <TableCaption class="sr-only">Payslip lines</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>Component</TableHead>
                  <TableHead class="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="line in currentRecord.lines" :key="line.code">
                  <TableCell>{{ line.label }}</TableCell>
                  <TableCell class="text-right tabular-nums">
                    {{ formatCurrency(currentRecord.currency, line.amount) }}
                  </TableCell>
                </TableRow>
                <TableRow class="net-row">
                  <TableCell>
                    <strong>Net</strong>
                  </TableCell>
                  <TableCell class="text-right tabular-nums">
                    <strong>{{ formatCurrency(currentRecord.currency, currentRecord.net_amount) }}</strong>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </section>
        </div>

        <section v-if="priorPeriods.length" class="payroll-section" aria-labelledby="prior-periods-title">
          <div class="section-heading">
            <div class="section-title">
              <FileTextIcon class="section-icon" :stroke-width="1.75" aria-hidden="true" />
              <h2 id="prior-periods-title">Prior periods</h2>
            </div>
          </div>
          <div class="hidden sm:block">
            <Table>
              <TableCaption class="sr-only">Prior pay periods</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>Period</TableHead>
                  <TableHead>Pay date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead class="text-right">Net</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="period in priorPeriods" :key="period.id">
                  <TableCell>
                    {{ formatDate(period.starts_on) }} to {{ formatDate(period.ends_on) }}
                  </TableCell>
                  <TableCell>{{ formatDate(period.pay_date) }}</TableCell>
                  <TableCell>
                    <StatusBadge :label="periodBadge(period)" :tone="statusTone(periodBadge(period))" />
                  </TableCell>
                  <TableCell class="text-right tabular-nums">
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
                <strong>{{ formatDate(period.starts_on) }} to {{ formatDate(period.ends_on) }}</strong>
                <StatusBadge :label="periodBadge(period)" :tone="statusTone(periodBadge(period))" />
              </div>
              <p class="m-0 text-[#495057]">Paid {{ formatDate(period.pay_date) }}</p>
              <strong v-if="recordFor(period)">
                {{
                  formatCurrency(recordFor(period)?.currency ?? 'INR', recordFor(period)?.net_amount)
                }}
              </strong>
            </article>
          </div>
        </section>
      </template>
    </div>
  </section>
</template>

<style scoped>
.payroll-sheet {
  margin-inline: auto;
  max-width: 1400px;
}

.payroll-body {
  display: grid;
  gap: 1.5rem;
}

.employee-payroll {
  display: grid;
  gap: 1.5rem;
}

.payroll-section {
  min-width: 0;
}

.selected-period {
  border-top: 1px solid var(--line);
  padding-top: 20px;
}

.section-heading,
.section-title,
.section-meta {
  display: flex;
  align-items: center;
}

.section-heading {
  min-height: 32px;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.section-title {
  gap: 12px;
  min-width: 0;
}

.section-title h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
  color: var(--ink);
}

.section-subtitle {
  margin: 4px 0 0;
  color: var(--muted-text);
  font-size: 13px;
  font-weight: 400;
  line-height: 1.5;
}

.section-icon {
  width: 20px;
  height: 20px;
  flex: none;
  color: var(--muted-text);
}

.section-meta {
  gap: 12px;
  color: var(--muted-text);
  font-size: 13px;
  flex-wrap: wrap;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0;
  margin: 0 0 16px;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--sheet);
}

.summary-grid > div {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
}

.summary-grid > div:nth-child(odd) {
  border-right: 1px solid var(--line);
}

.summary-grid > div:nth-last-child(-n + 2) {
  border-bottom: none;
}

.summary-grid dt {
  margin: 0;
  color: var(--muted-text);
  font-size: 12px;
  font-weight: 500;
}

.summary-grid dd {
  margin: 0;
  color: var(--ink);
  font-size: 14px;
  font-weight: 500;
}

.net-amount {
  font-size: 18px;
  font-weight: 700;
}

.net-row {
  border-top: 1px solid var(--line);
  background: #fbfbfc;
}

.salary-sheet {
  display: grid;
  gap: 16px;
}

.salary-employee {
  display: grid;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.salary-employee:first-of-type {
  border-top: none;
  padding-top: 0;
}

.salary-employee-name {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}

.salary-fields {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.salary-field {
  display: grid;
  gap: 5px;
  font-size: 13px;
  font-weight: 500;
}

.salary-field-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.salary-field-code {
  color: var(--muted-text);
  font-weight: 400;
  font-size: 12px;
}

.mobile-record-list {
  display: grid;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--sheet);
}

.mobile-record {
  display: grid;
  gap: 10px;
  padding: 16px;
}

.mobile-record + .mobile-record {
  border-top: 1px solid var(--line);
}

.mobile-record-row {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.mobile-record-label {
  color: var(--muted-text);
  font-size: 13px;
}

.mobile-record-value {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

@media (min-width: 640px) {
  .mobile-record-list {
    display: none;
  }

  .summary-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .summary-grid > div {
    border-right: 1px solid var(--line);
    border-bottom: none;
  }

  .summary-grid > div:last-child {
    border-right: none;
  }
}

@media (max-width: 639px) {
  .summary-grid > div:nth-child(odd) {
    border-right: 1px solid var(--line);
  }

  .summary-grid > div:nth-last-child(-n + 2) {
    border-bottom: none;
  }
}
</style>
