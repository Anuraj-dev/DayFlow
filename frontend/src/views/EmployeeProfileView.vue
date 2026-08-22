<script setup lang="ts">
import {
  ArrowLeftIcon,
  BanknoteIcon,
  BriefcaseBusinessIcon,
  FileTextIcon,
  MailIcon,
  MapPinIcon,
  PhoneIcon,
} from '@lucide/vue'
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import StatusBadge from '@/components/StatusBadge.vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { api, HttpError } from '@/api/client'
import { formatCurrency, formatDate, formatEnumLabel } from '@/lib/format'
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
const router = useRouter()
const session = useSessionStore()
const person = ref<EmployeeSummary | null>(null)
const payroll = ref<PayrollHome | null>(null)
const loading = ref(true)
const errorTitle = ref('')
const error = ref('')
const saveError = ref('')
const saveStatus = ref('')
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
  return (Object.keys(draft) as (keyof Draft)[]).filter(
    (key) => draft[key] !== baseline.value![key],
  )
})
const dirty = computed(() => dirtyKeys.value.length > 0)
const displayName = computed(() =>
  person.value ? `${person.value.first_name} ${person.value.last_name}` : 'Employee profile',
)
const initials = computed(() =>
  person.value
    ? `${person.value.first_name.charAt(0)}${person.value.last_name.charAt(0)}`.toUpperCase()
    : '',
)
const salaryRecord = computed(() => {
  const records = payroll.value?.records ?? []
  if (!person.value) return undefined
  if (!session.isHr) return records[0]
  return records.find((row) => row.employee_id === person.value?.id)
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
  payroll.value = null
  editing.value = false
  tab.value = 'personal'
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

function startEdit() {
  if (!person.value) return
  applyDraft(person.value)
  saveStatus.value = ''
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
  <section class="sheet profile-sheet">
    <div v-if="loading" class="profile-loading" role="status">Loading profile…</div>
    <Alert v-else-if="error" variant="destructive">
      <AlertTitle>{{ errorTitle || 'Error' }}</AlertTitle>
      <AlertDescription>{{ error }}</AlertDescription>
    </Alert>
    <template v-else-if="person">
      <div class="profile-actions">
        <Button
          v-if="session.isHr"
          type="button"
          variant="ghost"
          size="sm"
          @click="router.push('/employees')"
        >
          <ArrowLeftIcon class="size-4" aria-hidden="true" />
          People
        </Button>
        <span v-else></span>
        <div class="action-group">
          <StatusBadge v-if="dirty" label="Unsaved changes" :tone="statusTone('Unsaved changes')" />
          <Button v-if="!editing" type="button" variant="outline" @click="startEdit">
            {{ session.isHr ? 'Edit employee' : 'Edit profile' }}
          </Button>
          <Button v-if="editing" type="button" variant="secondary" @click="cancelEdit"
            >Discard</Button
          >
          <Button v-if="editing" type="button" :disabled="!dirty || saving" @click="save">
            {{ saving ? 'Saving…' : 'Save' }}
          </Button>
        </div>
      </div>

      <header class="profile-identity">
        <span class="profile-avatar" aria-hidden="true">{{ initials }}</span>
        <div class="identity-copy">
          <h1>{{ displayName }}</h1>
          <p>
            <span>{{ person.employee_code }}</span>
            <span aria-hidden="true">·</span>
            <span>{{ person.title ?? 'Title not set' }}</span>
          </p>
          <StatusBadge
            :label="employeeStatusLabel(draft.status)"
            :tone="statusTone(employeeStatusLabel(draft.status))"
          />
        </div>
        <dl class="identity-facts">
          <div>
            <dt><MailIcon aria-hidden="true" /> Work email</dt>
            <dd>{{ person.email ?? 'Not provided' }}</dd>
          </div>
          <div>
            <dt><MapPinIcon aria-hidden="true" /> Location</dt>
            <dd>{{ draft.location || 'Not provided' }}</dd>
          </div>
        </dl>
      </header>

      <form @submit.prevent="save">
        <p v-if="saveError" class="feedback-error" role="alert">{{ saveError }}</p>
        <p v-if="saveStatus" class="feedback-success" role="status">{{ saveStatus }}</p>

        <Tabs v-model="tab" class="profile-tabs">
          <TabsList class="profile-tab-list">
            <TabsTrigger value="personal" @click="tab = 'personal'">Personal</TabsTrigger>
            <TabsTrigger value="job" @click="tab = 'job'">Job</TabsTrigger>
            <TabsTrigger value="salary" @click="tab = 'salary'">Salary</TabsTrigger>
            <TabsTrigger value="documents" @click="tab = 'documents'">Documents</TabsTrigger>
          </TabsList>

          <TabsContent value="personal" class="tab-panel">
            <div class="panel-heading">
              <PhoneIcon aria-hidden="true" />
              <div>
                <h2>Personal details</h2>
                <p>
                  {{
                    session.isHr
                      ? 'Identity and contact information.'
                      : 'You can update your phone and address.'
                  }}
                </p>
              </div>
            </div>
            <div class="record-grid">
              <label>
                Employee code
                <Input :model-value="person.employee_code" disabled />
              </label>
              <label>
                Work email
                <Input :model-value="person.email ?? 'Not provided'" type="email" disabled />
              </label>
              <label>
                First name
                <Input v-model="draft.first_name" :disabled="!canEdit('first_name')" />
              </label>
              <label>
                Last name
                <Input v-model="draft.last_name" :disabled="!canEdit('last_name')" />
              </label>
              <label>
                Phone
                <Input v-model="draft.phone" :disabled="!canEdit('phone')" />
              </label>
              <label class="wide-field">
                Address
                <Textarea v-model="draft.address" :disabled="!canEdit('address')" />
              </label>
              <label v-if="session.isHr && editing">
                Employment status
                <NativeSelect v-model="draft.status" class="w-full">
                  <NativeSelectOption value="ACTIVE">Active</NativeSelectOption>
                  <NativeSelectOption value="INVITED">Invited</NativeSelectOption>
                  <NativeSelectOption value="INACTIVE">Inactive</NativeSelectOption>
                </NativeSelect>
              </label>
            </div>
          </TabsContent>

          <TabsContent value="job" class="tab-panel">
            <div class="panel-heading">
              <BriefcaseBusinessIcon aria-hidden="true" />
              <div>
                <h2>Job details</h2>
                <p>Current role and workplace information.</p>
              </div>
            </div>
            <div class="record-grid">
              <label>
                Title
                <Input v-model="draft.title" :disabled="!canEdit('title')" />
              </label>
              <label>
                Department
                <Input v-model="draft.department" :disabled="!canEdit('department')" />
              </label>
              <label>
                Employment type
                <Input v-if="canEdit('employment_type')" v-model="draft.employment_type" />
                <Input v-else :model-value="formatEnumLabel(draft.employment_type)" disabled />
              </label>
              <label>
                Location
                <Input v-model="draft.location" :disabled="!canEdit('location')" />
              </label>
              <label>
                Joined on
                <Input :model-value="formatDate(person.joined_on)" disabled />
              </label>
              <label>
                Role
                <Input :model-value="person.role === 'HR' ? 'HR officer' : 'Employee'" disabled />
              </label>
            </div>
          </TabsContent>

          <TabsContent value="salary" class="tab-panel">
            <div class="panel-heading">
              <BanknoteIcon aria-hidden="true" />
              <div>
                <h2>Salary</h2>
                <p>
                  {{
                    session.isHr
                      ? 'Latest payroll record for this employee.'
                      : 'Your latest published payroll record.'
                  }}
                </p>
              </div>
            </div>
            <div v-if="salaryRecord" class="salary-record">
              <div>
                <span>Net pay</span>
                <strong>{{
                  formatCurrency(salaryRecord.currency, salaryRecord.net_amount)
                }}</strong>
              </div>
              <StatusBadge
                :label="salaryRecord.published_at ? 'Published' : 'Draft'"
                :tone="statusTone(salaryRecord.published_at ? 'Published' : 'Draft')"
              />
            </div>
            <div v-else class="inline-empty">
              <BanknoteIcon aria-hidden="true" />
              <div>
                <h3>No payroll record</h3>
                <p>
                  {{
                    session.isHr
                      ? 'Set up this employee in Payroll.'
                      : 'No payslip has been published for this period.'
                  }}
                </p>
              </div>
            </div>
            <p class="panel-note">
              {{
                session.isHr
                  ? 'Edit salary inputs in Payroll before finalizing the period.'
                  : 'Salary details are read-only.'
              }}
            </p>
          </TabsContent>

          <TabsContent value="documents" class="tab-panel">
            <div class="panel-heading">
              <FileTextIcon aria-hidden="true" />
              <div>
                <h2>Documents</h2>
                <p>Employment records linked to this profile.</p>
              </div>
            </div>
            <div class="inline-empty">
              <FileTextIcon aria-hidden="true" />
              <div>
                <h3>Documents are not available yet</h3>
                <p>Private document access will appear here when uploads are enabled.</p>
              </div>
              <StatusBadge label="Missing document" :tone="statusTone('Missing document')" />
            </div>
          </TabsContent>
        </Tabs>
      </form>
    </template>
  </section>
</template>

<style scoped>
.profile-sheet {
  padding: 0;
}

.profile-loading {
  padding: 2rem 1.25rem;
  color: #495057;
}

.profile-actions {
  display: flex;
  min-height: 3.5rem;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.65rem 1.25rem;
  border-bottom: 1px solid #dee2e6;
  background: #f8f9fa;
}

.action-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
}

.profile-identity {
  display: grid;
  grid-template-columns: auto minmax(14rem, 1fr) minmax(19rem, 0.8fr);
  align-items: center;
  gap: 1.25rem;
  padding: 1.6rem 1.5rem;
}

.profile-avatar {
  display: grid;
  width: 5rem;
  height: 5rem;
  place-items: center;
  border: 1px solid #ded5dc;
  border-radius: 50%;
  background: #f2edf1;
  color: #714b67;
  font-size: 1.65rem;
  font-weight: 700;
}

.identity-copy h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.25;
}

.identity-copy p {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0.25rem 0 0.55rem;
  color: #495057;
}

.identity-facts {
  display: grid;
  gap: 0.75rem;
  margin: 0;
  padding-left: 1.25rem;
  border-left: 1px solid #dee2e6;
}

.identity-facts div {
  min-width: 0;
}

.identity-facts dt {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #495057;
  font-size: 12px;
  font-weight: 500;
}

.identity-facts dt svg {
  width: 0.95rem;
  height: 0.95rem;
}

.identity-facts dd {
  margin: 0.15rem 0 0 1.35rem;
  overflow-wrap: anywhere;
  font-weight: 500;
}

.profile-tabs {
  border-top: 1px solid #dee2e6;
}

.profile-tab-list {
  width: 100%;
  height: auto;
  justify-content: flex-start;
  overflow-x: auto;
  border-radius: 0;
  border-bottom: 1px solid #dee2e6;
  background: #fff;
  padding: 0 1.25rem;
}

.profile-tab-list button {
  min-height: 2.8rem;
  border-radius: 0;
}

.tab-panel {
  margin: 0;
  padding: 1.5rem;
}

.panel-heading {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  margin-bottom: 1.25rem;
}

.panel-heading > svg {
  width: 1.15rem;
  height: 1.15rem;
  margin-top: 0.2rem;
  color: #714b67;
}

.panel-heading h2,
.panel-heading p,
.inline-empty h3,
.inline-empty p {
  margin: 0;
}

.panel-heading h2 {
  font-size: 18px;
}

.panel-heading p,
.panel-note,
.inline-empty p {
  color: #495057;
}

.record-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 2rem;
  row-gap: 1rem;
  max-width: 64rem;
}

.record-grid label {
  display: grid;
  gap: 0.3rem;
  color: #495057;
  font-size: 13px;
  font-weight: 500;
}

.record-grid input:disabled,
.record-grid textarea:disabled {
  border-color: #e6e8ea;
  background: #f8f9fa;
  color: #212529;
  opacity: 1;
}

.wide-field {
  grid-column: 1 / -1;
}

.salary-record {
  display: flex;
  max-width: 40rem;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 0;
  border-top: 1px solid #dee2e6;
  border-bottom: 1px solid #dee2e6;
}

.salary-record span,
.salary-record strong {
  display: block;
}

.salary-record div > span {
  color: #495057;
  font-size: 13px;
}

.salary-record strong {
  margin-top: 0.2rem;
  font-size: 21px;
  font-variant-numeric: tabular-nums;
}

.panel-note {
  margin: 1rem 0 0;
}

.inline-empty {
  display: flex;
  max-width: 48rem;
  align-items: center;
  gap: 0.8rem;
  padding: 1rem;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  background: #f8f9fa;
}

.inline-empty > svg {
  width: 1.25rem;
  height: 1.25rem;
  flex: 0 0 auto;
  color: #495057;
}

.inline-empty > :last-child {
  margin-left: auto;
}

.feedback-error,
.feedback-success {
  margin: 1rem 1.25rem 0;
}

@media (max-width: 760px) {
  .profile-identity {
    grid-template-columns: auto minmax(0, 1fr);
    align-items: start;
    padding: 1.25rem 1rem;
  }

  .profile-avatar {
    width: 3.75rem;
    height: 3.75rem;
    font-size: 1.25rem;
  }

  .identity-copy h1 {
    font-size: 24px;
  }

  .identity-facts {
    grid-column: 1 / -1;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: 1rem 0 0;
    border-top: 1px solid #dee2e6;
    border-left: 0;
  }

  .identity-facts dd {
    margin-left: 0;
  }

  .record-grid {
    grid-template-columns: 1fr;
  }

  .wide-field {
    grid-column: auto;
  }
}

@media (max-width: 520px) {
  .profile-actions,
  .directory-footer {
    align-items: flex-start;
  }

  .profile-actions {
    padding-inline: 0.75rem;
  }

  .action-group {
    flex: 1;
  }

  .profile-tab-list,
  .tab-panel {
    padding-inline: 1rem;
  }

  .identity-facts {
    grid-template-columns: 1fr;
  }

  .inline-empty {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .inline-empty > :last-child {
    margin-left: 0;
  }
}
</style>
