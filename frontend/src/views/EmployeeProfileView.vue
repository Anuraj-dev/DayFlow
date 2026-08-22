<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { api, HttpError } from '@/api/client'
import { employeeStatusLabel, statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type { EmployeeStatus, EmployeeSummary, PayrollHome } from '@/types/domain'

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
const payroll = ref<PayrollHome | null>(null)
const loading = ref(true)
const errorTitle = ref('')
const error = ref('')
const saveError = ref('')
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

const salaryRecord = computed(() => {
  const records = payroll.value?.records ?? []
  if (!person.value) return records[0]
  return records.find((row) => row.employee_id === person.value?.id) ?? records[0]
})

function canEdit(field: keyof Draft): boolean {
  return editing.value && allowedFields.value.has(field)
}

async function load() {
  loading.value = true
  error.value = ''
  errorTitle.value = ''
  saveError.value = ''
  person.value = null
  editing.value = false
  const employeeId = String(route.params.employeeId)
  try {
    const row = await api<EmployeeSummary>(`/api/employees/${employeeId}`)
    person.value = row
    applyDraft(row)
    payroll.value = await api<PayrollHome>('/api/payroll').catch(() => null)
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
  } catch (err) {
    saveError.value = err instanceof HttpError ? err.detail : 'Could not save profile.'
  } finally {
    saving.value = false
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
        <Button type="button" variant="outline" :disabled="editing" @click="startEdit">Edit</Button>
        <Button v-if="editing" type="button" variant="secondary" @click="cancelEdit">Discard</Button>
        <Button type="button" :disabled="!editing || !dirty || saving" @click="save">Save</Button>
      </template>
    </PageHeader>
    <p v-if="loading">Loading profile…</p>
    <Alert v-else-if="error" variant="destructive">
      <AlertTitle>{{ errorTitle || 'Error' }}</AlertTitle>
      <AlertDescription>{{ error }}</AlertDescription>
    </Alert>
    <form v-else-if="person" class="grid gap-4" @submit.prevent="save">
      <p v-if="saveError" role="alert">{{ saveError }}</p>
      <Tabs v-model="tab">
        <TabsList>
          <TabsTrigger value="personal">Personal</TabsTrigger>
          <TabsTrigger value="job">Job</TabsTrigger>
          <TabsTrigger value="salary">Salary</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
        </TabsList>
        <TabsContent value="personal" force-mount class="grid max-w-xl gap-[5px] pt-4">
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
            <Input :model-value="person.email ?? ''" type="email" disabled />
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
        <TabsContent value="job" force-mount class="grid max-w-xl gap-[5px] pt-4">
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
            <Input v-model="draft.employment_type" :disabled="!canEdit('employment_type')" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Location
            <Input v-model="draft.location" :disabled="!canEdit('location')" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Joined on
            <Input :model-value="person.joined_on ?? ''" disabled />
          </label>
        </TabsContent>
        <TabsContent value="salary" force-mount class="grid max-w-xl gap-3 pt-4">
          <p v-if="salaryRecord">
            {{ salaryRecord.currency }} {{ salaryRecord.net_amount }}
            <StatusBadge
              :label="salaryRecord.published_at ? 'Published' : 'Draft'"
              :tone="statusTone(salaryRecord.published_at ? 'Published' : 'Draft')"
            />
          </p>
          <p v-else>No published payslip.</p>
          <p class="text-[#495057]">
            {{
              session.isHr
                ? 'Salary is read-only here. Edit salary inputs in Payroll before a period is finalized.'
                : 'Salary is read-only for employees.'
            }}
          </p>
        </TabsContent>
        <TabsContent value="documents" force-mount class="grid gap-3 pt-4">
          <StatusBadge label="Missing document" :tone="statusTone('Missing document')" />
          <p>
            Document upload is deferred. This tab stays visible so the surface is not silently omitted.
          </p>
        </TabsContent>
      </Tabs>
    </form>
  </section>
</template>
