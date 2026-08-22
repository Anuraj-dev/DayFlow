<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { api, HttpError } from '@/api/client'
import { formatCurrency, formatDate, formatEnumLabel } from '@/lib/format'
import { employeeStatusLabel, statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type { EmployeeSalary, EmployeeStatus, EmployeeSummary, SalaryLine } from '@/types/domain'

type Draft = {
  first_name: string
  last_name: string
  phone: string
  address: string
  status: EmployeeStatus
  title: string
  department: string
  employment_type: string
  location: string
}

const EMPLOYEE_FIELDS = new Set<keyof Draft>(['phone', 'address'])
const HR_FIELDS = new Set<keyof Draft>([
  'first_name',
  'last_name',
  'phone',
  'address',
  'status',
  'title',
  'department',
  'employment_type',
  'location',
])

const route = useRoute()
const session = useSessionStore()
const person = ref<EmployeeSummary | null>(null)
const salary = ref<EmployeeSalary | null>(null)
const loading = ref(true)
const errorTitle = ref('')
const error = ref('')
const saveError = ref('')
const saveStatus = ref('')
const salaryError = ref('')
const salaryStatus = ref('')
const salaryHidden = ref(false)
const salaryMissing = ref(false)
const savingSalary = ref(false)
const salaryDraftWage = ref('')
const salaryDraftRates = reactive<Record<string, string>>({})
const salaryDraftAmounts = reactive<Record<string, string>>({})
const tab = ref('personal')
const editing = ref(false)
const saving = ref(false)
const draft = reactive<Draft>({
  first_name: '',
  last_name: '',
  phone: '',
  address: '',
  status: 'ACTIVE',
  title: '',
  department: '',
  employment_type: '',
  location: '',
})

const allowedFields = computed(() => (session.isHr ? HR_FIELDS : EMPLOYEE_FIELDS))

function snapshotFrom(row: EmployeeSummary): Draft {
  return {
    first_name: row.first_name,
    last_name: row.last_name,
    phone: row.phone ?? '',
    address: row.address ?? '',
    status: row.status,
    title: row.title ?? '',
    department: row.department ?? '',
    employment_type: row.employment_type ?? '',
    location: row.location ?? '',
  }
}

function applyDraft(row: EmployeeSummary) {
  Object.assign(draft, snapshotFrom(row))
}

const baseline = computed(() => (person.value ? snapshotFrom(person.value) : null))

const dirtyKeys = computed<(keyof Draft)[]>(() => {
  if (!baseline.value) return []
  return (Object.keys(draft) as (keyof Draft)[]).filter((key) => draft[key] !== baseline.value![key])
})

const dirty = computed(() => dirtyKeys.value.length > 0)

const displayName = computed(() =>
  person.value ? `${person.value.first_name} ${person.value.last_name}` : 'Profile',
)

function calculationLabel(type: string): string {
  if (type === 'PERCENT_OF_WAGE') return '% of wage'
  if (type === 'PERCENT_OF_BASIC') return '% of Basic'
  if (type === 'REMAINDER') return 'Remainder'
  return 'Fixed amount'
}

function lineStatus(line: SalaryLine): string {
  if (line.kind === 'EMPLOYER') return 'Employer contribution'
  if (line.kind === 'DEDUCTION') return 'Deduction'
  if (!line.editable) return 'Computed'
  return 'Editable'
}

function applySalaryDraft(row: EmployeeSalary) {
  salaryDraftWage.value = row.monthly_wage
  for (const key of Object.keys(salaryDraftRates)) delete salaryDraftRates[key]
  for (const key of Object.keys(salaryDraftAmounts)) delete salaryDraftAmounts[key]
  for (const line of row.lines) {
    if (line.calculation_type === 'FIXED') salaryDraftAmounts[line.code] = line.amount
    else if (line.rate != null) salaryDraftRates[line.code] = line.rate
  }
}

function canEdit(field: keyof Draft): boolean {
  return editing.value && allowedFields.value.has(field)
}

async function load() {
  loading.value = true
  error.value = ''
  errorTitle.value = ''
  saveError.value = ''
  saveStatus.value = ''
  person.value = null
  salary.value = null
  salaryHidden.value = false
  salaryMissing.value = false
  salaryError.value = ''
  salaryStatus.value = ''
  editing.value = false
  const employeeId = String(route.params.employeeId)
  try {
    const row = await api<EmployeeSummary>(`/api/employees/${employeeId}`)
    person.value = row
    applyDraft(row)
    try {
      const breakdown = await api<EmployeeSalary>(`/api/payroll/employees/${employeeId}/salary`)
      salary.value = breakdown
      applySalaryDraft(breakdown)
    } catch (err) {
      if (err instanceof HttpError && err.status === 403) {
        salaryHidden.value = true
      } else if (err instanceof HttpError && err.status === 404) {
        salaryMissing.value = true
        salaryDraftWage.value = '50000.00'
      } else {
        salaryError.value = err instanceof HttpError ? err.detail : 'Could not load salary.'
      }
    }
  } catch (err) {
    if (err instanceof HttpError && err.status === 403) {
      errorTitle.value = 'Access denied'
      error.value = err.detail
    } else {
      errorTitle.value = 'Could not load profile'
      error.value = err instanceof HttpError ? err.detail : 'Could not load profile.'
    }
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!person.value || !dirty.value) return
  saving.value = true
  saveError.value = ''
  saveStatus.value = ''
  const payload: Record<string, string> = {}
  for (const key of dirtyKeys.value) {
    if (allowedFields.value.has(key)) payload[key] = draft[key]
  }
  try {
    person.value = await api<EmployeeSummary>(`/api/employees/${person.value.id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    applyDraft(person.value)
    editing.value = false
    saveStatus.value = 'Profile saved.'
  } catch (err) {
    saveError.value = err instanceof HttpError ? err.detail : 'Could not save profile.'
  } finally {
    saving.value = false
  }
}

async function saveSalary() {
  if (!person.value || !session.isHr) return
  savingSalary.value = true
  salaryError.value = ''
  salaryStatus.value = ''
  const components = (salary.value?.lines ?? [])
    .filter((line) => line.editable)
    .map((line) =>
      line.calculation_type === 'FIXED'
        ? { code: line.code, calculation_type: line.calculation_type, amount: salaryDraftAmounts[line.code] ?? line.amount }
        : { code: line.code, calculation_type: line.calculation_type, rate: salaryDraftRates[line.code] ?? line.rate },
    )
  try {
    const breakdown = await api<EmployeeSalary>(`/api/payroll/employees/${person.value.id}/salary`, {
      method: 'PATCH',
      body: JSON.stringify({
        monthly_wage: salaryDraftWage.value,
        components,
      }),
    })
    salary.value = breakdown
    salaryMissing.value = false
    applySalaryDraft(breakdown)
    salaryStatus.value = 'Salary saved.'
  } catch (err) {
    salaryError.value = err instanceof HttpError ? err.detail : 'Could not save salary.'
  } finally {
    savingSalary.value = false
  }
}

function startEdit() {
  if (!person.value) return
  applyDraft(person.value)
  editing.value = true
}

function cancelEdit() {
  if (person.value) applyDraft(person.value)
  editing.value = false
  saveError.value = ''
  saveStatus.value = ''
}

watch(
  () => route.params.employeeId,
  () => {
    void load()
  },
  { immediate: true },
)
</script>

<template>
  <section class="sheet">
    <PageHeader
      :title="errorTitle === 'Access denied' ? 'Access denied' : displayName"
      :description="person ? 'Personal, job, salary, and documents.' : undefined"
    >
      <template v-if="person">
        <StatusBadge
          v-if="dirty"
          label="Unsaved changes"
          :tone="statusTone('Unsaved changes')"
        />
        <Button v-if="!editing" type="button" variant="outline" @click="startEdit">Edit</Button>
        <Button v-if="editing" type="button" variant="secondary" @click="cancelEdit">Discard</Button>
        <Button v-if="editing" type="button" :disabled="!dirty || saving" @click="save">Save</Button>
      </template>
    </PageHeader>
    <p v-if="loading">Loading profile…</p>
    <Alert v-else-if="error" variant="destructive">
      <AlertTitle>{{ errorTitle || 'Error' }}</AlertTitle>
      <AlertDescription>{{ error }}</AlertDescription>
    </Alert>
    <form v-else-if="person" class="grid gap-4" @submit.prevent="save">
      <p v-if="saveError" role="alert">{{ saveError }}</p>
      <p v-if="saveStatus" class="feedback-success" role="status">{{ saveStatus }}</p>
      <Tabs v-model="tab">
        <TabsList class="h-auto w-full justify-start overflow-x-auto">
          <TabsTrigger value="personal" @click="tab = 'personal'">Personal</TabsTrigger>
          <TabsTrigger value="job" @click="tab = 'job'">Job</TabsTrigger>
          <TabsTrigger value="salary" @click="tab = 'salary'">Salary</TabsTrigger>
          <TabsTrigger value="documents" @click="tab = 'documents'">Documents</TabsTrigger>
        </TabsList>
        <TabsContent value="personal" class="grid max-w-xl gap-[5px] pt-4">
          <label class="grid gap-1 text-sm font-medium">
            Employee code
            <Input :model-value="person.employee_code" disabled />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            First name
            <Input v-model="draft.first_name" :disabled="!canEdit('first_name')" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Last name
            <Input v-model="draft.last_name" :disabled="!canEdit('last_name')" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Work email
            <Input :model-value="person.email ?? 'Not provided'" type="email" disabled />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Phone
            <Input v-model="draft.phone" :disabled="!canEdit('phone')" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Address
            <Textarea v-model="draft.address" :disabled="!canEdit('address')" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Employment status
            <NativeSelect v-model="draft.status" class="w-full" :disabled="!canEdit('status')">
              <NativeSelectOption value="ACTIVE">Active</NativeSelectOption>
              <NativeSelectOption value="INVITED">Invited</NativeSelectOption>
              <NativeSelectOption value="INACTIVE">Inactive</NativeSelectOption>
            </NativeSelect>
          </label>
          <p class="text-sm text-[#495057]">
            Status
            <StatusBadge
              :label="employeeStatusLabel(draft.status)"
              :tone="statusTone(employeeStatusLabel(draft.status))"
            />
          </p>
        </TabsContent>
        <TabsContent value="job" class="grid max-w-xl gap-[5px] pt-4">
          <label class="grid gap-1 text-sm font-medium">
            Title
            <Input v-model="draft.title" :disabled="!canEdit('title')" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Department
            <Input v-model="draft.department" :disabled="!canEdit('department')" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Employment type
            <Input
              v-if="canEdit('employment_type')"
              v-model="draft.employment_type"
            />
            <Input v-else :model-value="formatEnumLabel(draft.employment_type)" disabled />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Location
            <Input v-model="draft.location" :disabled="!canEdit('location')" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Joined on
            <Input :model-value="formatDate(person.joined_on)" disabled />
          </label>
        </TabsContent>
        <TabsContent value="salary" class="grid gap-3 pt-4">
          <p v-if="salaryError" role="alert">{{ salaryError }}</p>
          <p v-if="salaryStatus" class="feedback-success" role="status">{{ salaryStatus }}</p>
          <p v-if="salaryHidden">Salary is hidden.</p>
          <template v-else-if="salary || (session.isHr && salaryMissing)">
            <p class="m-0 text-[#495057]">
              {{
                session.isHr
                  ? 'HR sets monthly wage and editable rates. Remainder, PF, and professional tax are computed.'
                  : 'Computed monthly breakdown. Coworker salary stays hidden.'
              }}
            </p>
            <label class="grid max-w-xs gap-1 text-sm font-medium">
              Monthly wage
              <Input
                v-model="salaryDraftWage"
                inputmode="decimal"
                :disabled="!session.isHr"
              />
            </label>
            <p v-if="salary" class="m-0">
              Net {{ formatCurrency(salary.currency, salary.net_amount) }}
              <StatusBadge label="Computed" :tone="statusTone('Computed')" />
            </p>
            <Table v-if="salary">
              <TableCaption class="sr-only">Salary structure</TableCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>Component</TableHead>
                  <TableHead>Basis</TableHead>
                  <TableHead>Input</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-for="line in salary.lines" :key="line.code">
                  <TableCell>{{ line.name }}</TableCell>
                  <TableCell>{{ calculationLabel(line.calculation_type) }}</TableCell>
                  <TableCell>
                    <label
                      v-if="session.isHr && line.editable && line.calculation_type === 'FIXED'"
                      class="grid gap-1 text-sm font-medium"
                    >
                      {{ line.code }} amount
                      <Input v-model="salaryDraftAmounts[line.code]" inputmode="decimal" />
                    </label>
                    <label
                      v-else-if="session.isHr && line.editable"
                      class="grid gap-1 text-sm font-medium"
                    >
                      {{ line.code }} rate
                      <Input v-model="salaryDraftRates[line.code]" inputmode="decimal" />
                    </label>
                    <span v-else>{{ line.rate ?? '—' }}</span>
                  </TableCell>
                  <TableCell>{{ formatCurrency(salary.currency, line.amount) }}</TableCell>
                  <TableCell>
                    <StatusBadge :label="lineStatus(line)" :tone="statusTone(lineStatus(line))" />
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
            <Button
              v-if="session.isHr"
              type="button"
              :disabled="savingSalary"
              @click="saveSalary"
            >
              Save salary
            </Button>
          </template>
          <p v-else>No salary configured.</p>
        </TabsContent>
        <TabsContent value="documents" class="grid gap-3 pt-4">
          <StatusBadge label="Missing document" :tone="statusTone('Missing document')" />
          <p>
            Document uploads are not available yet. HR and employees will access private documents here when enabled.
          </p>
        </TabsContent>
      </Tabs>
    </form>
  </section>
</template>
