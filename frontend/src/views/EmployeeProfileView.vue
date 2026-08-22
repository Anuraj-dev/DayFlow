<script setup lang="ts">
import { MailIcon, MapPinIcon, PhoneIcon } from '@lucide/vue'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import StatusBadge from '@/components/StatusBadge.vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
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
  date_of_birth: string
  nationality: string
  gender: string
  marital_status: string
  personal_email: string
  bank_account_number: string
  bank_name: string
  ifsc: string
  pan: string
  uan: string
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
  'date_of_birth',
  'nationality',
  'gender',
  'marital_status',
  'personal_email',
  'bank_account_number',
  'bank_name',
  'ifsc',
  'pan',
  'uan',
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
const controlActionsReady = ref(false)
const currentPassword = ref('')
const newPassword = ref('')
const passwordError = ref('')
const passwordStatus = ref('')
const savingPassword = ref(false)
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
  date_of_birth: '',
  nationality: '',
  gender: '',
  marital_status: '',
  personal_email: '',
  bank_account_number: '',
  bank_name: '',
  ifsc: '',
  pan: '',
  uan: '',
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
    date_of_birth: row.date_of_birth ?? '',
    nationality: row.nationality ?? '',
    gender: row.gender ?? '',
    marital_status: row.marital_status ?? '',
    personal_email: row.personal_email ?? '',
    bank_account_number: row.bank_account_number ?? '',
    bank_name: row.bank_name ?? '',
    ifsc: row.ifsc ?? '',
    pan: row.pan ?? '',
    uan: row.uan ?? '',
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

const pageHeading = computed(() =>
  errorTitle.value === 'Access denied' ? 'Access denied' : displayName.value,
)

const isSelf = computed(
  () => Boolean(session.user?.employee_id) && session.user?.employee_id === person.value?.id,
)

const canViewPrivate = computed(() => session.isHr || isSelf.value)

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

const useIdentityColumn = computed(() => !session.isHr)

const profileInitials = computed(() => {
  if (!person.value) return ''
  const first = person.value.first_name.trim().charAt(0)
  const last = person.value.last_name.trim().charAt(0)
  return `${first}${last}`.toUpperCase() || person.value.employee_code.slice(0, 2).toUpperCase()
})

const roleLabel = computed(() => {
  if (person.value?.role === 'HR') return 'HR'
  if (person.value?.role === 'EMPLOYEE') return 'Employee'
  return person.value?.role ?? null
})

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
  passwordError.value = ''
  passwordStatus.value = ''
  currentPassword.value = ''
  newPassword.value = ''
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
  const payload: Record<string, string | null> = {}
  for (const key of dirtyKeys.value) {
    if (allowedFields.value.has(key)) payload[key] = draft[key] === '' ? null : draft[key]
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

async function changePassword() {
  savingPassword.value = true
  passwordError.value = ''
  passwordStatus.value = ''
  try {
    const result = await api<{ detail: string }>('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword.value,
        new_password: newPassword.value,
      }),
    })
    currentPassword.value = ''
    newPassword.value = ''
    passwordStatus.value = result.detail
  } catch (err) {
    passwordError.value = err instanceof HttpError ? err.detail : 'Could not change password.'
  } finally {
    savingPassword.value = false
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

onMounted(async () => {
  await nextTick()
  controlActionsReady.value = Boolean(document.getElementById('control-actions'))
})

watch(
  () => route.params.employeeId,
  () => {
    void load()
  },
  { immediate: true },
)
</script>

<template>
  <section class="sheet employee-profile">
    <Teleport v-if="controlActionsReady && person" defer to="#control-actions">
      <div class="flex flex-wrap items-center gap-2">
        <StatusBadge
          v-if="dirty"
          label="Unsaved changes"
          :tone="statusTone('Unsaved changes')"
        />
        <Button v-if="!editing" type="button" @click="startEdit">Edit</Button>
        <Button v-if="editing" type="button" variant="secondary" @click="cancelEdit">Discard</Button>
        <Button v-if="editing" type="button" :disabled="!dirty || saving" @click="save">Save</Button>
      </div>
    </Teleport>

    <p v-if="loading">Loading profile…</p>
    <Alert v-else-if="error" variant="destructive">
      <AlertTitle>{{ errorTitle || 'Error' }}</AlertTitle>
      <AlertDescription>{{ error }}</AlertDescription>
      <h1 class="sr-only">{{ pageHeading }}</h1>
    </Alert>

    <div v-else-if="person" class="grid gap-4">
      <div
        v-if="!controlActionsReady"
        class="flex flex-wrap items-center justify-end gap-2 border-b border-[#DEE2E6] pb-3"
      >
        <StatusBadge
          v-if="dirty"
          label="Unsaved changes"
          :tone="statusTone('Unsaved changes')"
        />
        <Button v-if="!editing" type="button" @click="startEdit">Edit</Button>
        <Button v-if="editing" type="button" variant="secondary" @click="cancelEdit">Discard</Button>
        <Button v-if="editing" type="button" :disabled="!dirty || saving" @click="save">Save</Button>
      </div>

      <p v-if="saveError" role="alert">{{ saveError }}</p>
      <p v-if="saveStatus" class="feedback-success" role="status">{{ saveStatus }}</p>

      <!-- HR: identity header strip -->
      <header
        v-if="!useIdentityColumn"
        class="identity-header flex flex-wrap items-start gap-4 border-b border-[#DEE2E6] pb-4"
      >
        <Avatar size="lg" class="size-16 bg-[#F8F9FA] text-base font-medium text-[#495057]">
          <AvatarFallback>{{ profileInitials }}</AvatarFallback>
        </Avatar>
        <div class="min-w-0 flex-1">
          <h1 class="m-0 text-[24px] leading-[1.4] font-bold text-[#212529] sm:text-[28px]">
            {{ displayName }}
          </h1>
          <p class="m-0 mt-1 text-sm text-[#495057]">
            {{ person.employee_code }}
            <span v-if="roleLabel"> · {{ roleLabel }}</span>
            <span v-if="person.title"> · {{ person.title }}</span>
          </p>
          <div class="mt-2 flex flex-wrap items-center gap-2">
            <StatusBadge
              :label="employeeStatusLabel(draft.status)"
              :tone="statusTone(employeeStatusLabel(draft.status))"
            />
          </div>
          <ul class="identity-facts mt-3 grid gap-1.5 text-sm text-[#495057]">
            <li v-if="person.email" class="flex items-center gap-2">
              <MailIcon class="size-4 shrink-0" :stroke-width="1.75" aria-hidden="true" />
              <span>{{ person.email }}</span>
            </li>
            <li v-if="draft.phone" class="flex items-center gap-2">
              <PhoneIcon class="size-4 shrink-0" :stroke-width="1.75" aria-hidden="true" />
              <span>{{ draft.phone }}</span>
            </li>
            <li v-if="draft.location || draft.address" class="flex items-center gap-2">
              <MapPinIcon class="size-4 shrink-0" :stroke-width="1.75" aria-hidden="true" />
              <span>{{ draft.location || draft.address }}</span>
            </li>
          </ul>
        </div>
      </header>

      <div
        class="profile-body"
        :class="useIdentityColumn ? 'profile-body--column' : 'profile-body--header'"
      >
        <!-- Employee: identity side column -->
        <aside v-if="useIdentityColumn" class="identity-column">
          <Avatar size="lg" class="size-20 bg-[#F8F9FA] text-lg font-medium text-[#495057]">
            <AvatarFallback>{{ profileInitials }}</AvatarFallback>
          </Avatar>
          <h1 class="m-0 mt-3 text-[21px] leading-[1.4] font-bold text-[#212529]">
            {{ displayName }}
          </h1>
          <p class="m-0 mt-1 text-sm text-[#495057]">{{ person.employee_code }}</p>
          <div class="mt-2">
            <StatusBadge
              :label="employeeStatusLabel(draft.status)"
              :tone="statusTone(employeeStatusLabel(draft.status))"
            />
          </div>
          <ul class="identity-facts mt-4 grid gap-2 text-sm text-[#495057]">
            <li v-if="person.email" class="flex items-start gap-2">
              <MailIcon class="mt-0.5 size-4 shrink-0" :stroke-width="1.75" aria-hidden="true" />
              <span class="min-w-0 break-words">{{ person.email }}</span>
            </li>
            <li v-if="draft.phone" class="flex items-start gap-2">
              <PhoneIcon class="mt-0.5 size-4 shrink-0" :stroke-width="1.75" aria-hidden="true" />
              <span class="min-w-0 break-words">{{ draft.phone }}</span>
            </li>
            <li v-if="draft.location || draft.address" class="flex items-start gap-2">
              <MapPinIcon class="mt-0.5 size-4 shrink-0" :stroke-width="1.75" aria-hidden="true" />
              <span class="min-w-0 break-words">{{ draft.location || draft.address }}</span>
            </li>
          </ul>
        </aside>

        <div class="profile-tabs min-w-0">
          <Tabs v-model="tab">
            <TabsList class="h-auto w-full justify-start overflow-x-auto">
              <TabsTrigger value="personal" @click="tab = 'personal'">Personal</TabsTrigger>
              <TabsTrigger value="job" @click="tab = 'job'">Job</TabsTrigger>
              <TabsTrigger v-if="canViewPrivate" value="private" @click="tab = 'private'">Private</TabsTrigger>
              <TabsTrigger v-if="canViewPrivate" value="bank" @click="tab = 'bank'">Bank</TabsTrigger>
              <TabsTrigger value="salary" @click="tab = 'salary'">Salary</TabsTrigger>
              <TabsTrigger value="documents" @click="tab = 'documents'">Documents</TabsTrigger>
              <TabsTrigger v-if="isSelf" value="security" @click="tab = 'security'">Security</TabsTrigger>
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
            <TabsContent v-if="canViewPrivate" value="private" class="grid max-w-xl gap-[5px] pt-4">
              <label class="grid gap-1 text-sm font-medium">
                Date of birth
                <Input v-model="draft.date_of_birth" type="date" :disabled="!canEdit('date_of_birth')" />
              </label>
              <label class="grid gap-1 text-sm font-medium">
                Nationality
                <Input v-model="draft.nationality" :disabled="!canEdit('nationality')" />
              </label>
              <label class="grid gap-1 text-sm font-medium">
                Gender
                <NativeSelect v-model="draft.gender" class="w-full" :disabled="!canEdit('gender')">
                  <NativeSelectOption value="">Not provided</NativeSelectOption>
                  <NativeSelectOption value="MALE">Male</NativeSelectOption>
                  <NativeSelectOption value="FEMALE">Female</NativeSelectOption>
                  <NativeSelectOption value="OTHER">Other</NativeSelectOption>
                  <NativeSelectOption value="PREFER_NOT_TO_SAY">Prefer not to say</NativeSelectOption>
                </NativeSelect>
              </label>
              <label class="grid gap-1 text-sm font-medium">
                Marital status
                <NativeSelect v-model="draft.marital_status" class="w-full" :disabled="!canEdit('marital_status')">
                  <NativeSelectOption value="">Not provided</NativeSelectOption>
                  <NativeSelectOption value="SINGLE">Single</NativeSelectOption>
                  <NativeSelectOption value="MARRIED">Married</NativeSelectOption>
                  <NativeSelectOption value="DIVORCED">Divorced</NativeSelectOption>
                  <NativeSelectOption value="WIDOWED">Widowed</NativeSelectOption>
                  <NativeSelectOption value="OTHER">Other</NativeSelectOption>
                </NativeSelect>
              </label>
              <label class="grid gap-1 text-sm font-medium">
                Personal email
                <Input v-model="draft.personal_email" type="email" :disabled="!canEdit('personal_email')" />
              </label>
            </TabsContent>
            <TabsContent v-if="canViewPrivate" value="bank" class="grid max-w-xl gap-[5px] pt-4">
              <label class="grid gap-1 text-sm font-medium">
                Bank account number
                <Input v-model="draft.bank_account_number" :disabled="!canEdit('bank_account_number')" />
              </label>
              <label class="grid gap-1 text-sm font-medium">
                Bank name
                <Input v-model="draft.bank_name" :disabled="!canEdit('bank_name')" />
              </label>
              <label class="grid gap-1 text-sm font-medium">
                IFSC
                <Input v-model="draft.ifsc" :disabled="!canEdit('ifsc')" />
              </label>
              <label class="grid gap-1 text-sm font-medium">
                PAN
                <Input v-model="draft.pan" :disabled="!canEdit('pan')" />
              </label>
              <label class="grid gap-1 text-sm font-medium">
                UAN
                <Input v-model="draft.uan" :disabled="!canEdit('uan')" />
              </label>
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
                  <Input v-model="salaryDraftWage" inputmode="decimal" :disabled="!session.isHr" />
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
                <Button v-if="session.isHr" type="button" :disabled="savingSalary" @click="saveSalary">
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
            <TabsContent v-if="isSelf" value="security" class="grid max-w-xl gap-[5px] pt-4">
              <form class="grid gap-[5px]" @submit.prevent="changePassword">
                <p v-if="passwordError" role="alert">{{ passwordError }}</p>
                <p v-if="passwordStatus" class="feedback-success" role="status">{{ passwordStatus }}</p>
                <label class="grid gap-1 text-sm font-medium">
                  Current password
                  <Input v-model="currentPassword" type="password" autocomplete="current-password" />
                </label>
                <label class="grid gap-1 text-sm font-medium">
                  New password
                  <Input v-model="newPassword" type="password" autocomplete="new-password" />
                </label>
                <Button type="submit" :disabled="savingPassword || !currentPassword || !newPassword">
                  Change password
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.profile-body--column {
  display: grid;
  gap: 1.5rem;
}

@media (min-width: 768px) {
  .profile-body--column {
    grid-template-columns: minmax(12rem, 16rem) minmax(0, 1fr);
    align-items: start;
  }
}

.identity-column {
  min-width: 0;
  padding-bottom: 1rem;
  border-bottom: 1px solid #dee2e6;
}

@media (min-width: 768px) {
  .identity-column {
    border-bottom: none;
    border-right: 1px solid #dee2e6;
    padding-bottom: 0;
    padding-right: 1.5rem;
  }
}

.identity-facts {
  margin: 0;
  padding: 0;
  list-style: none;
}
</style>
