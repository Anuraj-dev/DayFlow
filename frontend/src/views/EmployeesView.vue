<script setup lang="ts">
import {
  CheckIcon,
  ChevronRightIcon,
  CopyIcon,
  PlusIcon,
  SearchIcon,
  UsersRoundIcon,
} from '@lucide/vue'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
import { api } from '@/api/client'
import { employeeStatusLabel, statusTone } from '@/lib/status'
import type { EmployeeStatus, EmployeeSummary } from '@/types/domain'

type NewEmployeeDraft = {
  first_name: string
  last_name: string
  email: string
  title: string
  department: string
  employment_type: string
  location: string
  phone: string
}

type EmployeeCreateResult = EmployeeSummary & {
  initial_password: string
}

const router = useRouter()
const employees = ref<EmployeeSummary[]>([])
const loading = ref(true)
const error = ref('')
const query = ref('')
const departmentFilter = ref('all')
const statusFilter = ref<'all' | EmployeeStatus>('all')
const sortBy = ref<'name' | 'code' | 'department'>('name')
const page = ref(1)
const addEmployeeOpen = ref(false)
const creating = ref(false)
const createError = ref('')
const createdEmployee = ref<EmployeeCreateResult | null>(null)
const copiedCredential = ref<'login' | 'password' | 'all' | ''>('')
const newEmployee = reactive<NewEmployeeDraft>({
  first_name: '',
  last_name: '',
  email: '',
  title: '',
  department: '',
  employment_type: 'FULL_TIME',
  location: 'Office',
  phone: '',
})
const PAGE_SIZE = 20

const departments = computed(() =>
  [
    ...new Set(
      employees.value
        .map((row) => row.department)
        .filter((value): value is string => Boolean(value)),
    ),
  ].sort((a, b) => a.localeCompare(b)),
)

function searchableText(row: EmployeeSummary): string {
  return [
    row.employee_code,
    row.first_name,
    row.last_name,
    row.email,
    row.phone,
    row.role,
    row.title,
    row.department,
    row.employment_type,
    row.location,
  ]
    .filter(Boolean)
    .join(' ')
    .toLocaleLowerCase()
}

const visible = computed(() => {
  const term = query.value.trim().toLocaleLowerCase()
  return employees.value
    .filter((row) => {
      if (statusFilter.value !== 'all' && row.status !== statusFilter.value) return false
      if (departmentFilter.value !== 'all' && row.department !== departmentFilter.value)
        return false
      return !term || searchableText(row).includes(term)
    })
    .sort((a, b) => {
      if (sortBy.value === 'code') return a.employee_code.localeCompare(b.employee_code)
      if (sortBy.value === 'department')
        return (a.department ?? '').localeCompare(b.department ?? '')
      return `${a.first_name} ${a.last_name}`.localeCompare(`${b.first_name} ${b.last_name}`)
    })
})

const pageCount = computed(() => Math.max(1, Math.ceil(visible.value.length / PAGE_SIZE)))
const pagedEmployees = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE
  return visible.value.slice(start, start + PAGE_SIZE)
})
const rangeStart = computed(() => (visible.value.length ? (page.value - 1) * PAGE_SIZE + 1 : 0))
const rangeEnd = computed(() => Math.min(page.value * PAGE_SIZE, visible.value.length))
const filtersActive = computed(
  () =>
    Boolean(query.value.trim()) || departmentFilter.value !== 'all' || statusFilter.value !== 'all',
)

function initials(person: EmployeeSummary): string {
  return `${person.first_name.charAt(0)}${person.last_name.charAt(0)}`.toUpperCase()
}

function roleLabel(person: EmployeeSummary): string {
  return person.role === 'HR' ? 'HR officer' : 'Employee'
}

function clearFilters() {
  query.value = ''
  departmentFilter.value = 'all'
  statusFilter.value = 'all'
  sortBy.value = 'name'
}

function openProfile(person: EmployeeSummary) {
  void router.push(`/employees/${person.id}`)
}

function resetCreateForm() {
  Object.assign(newEmployee, {
    first_name: '',
    last_name: '',
    email: '',
    title: '',
    department: '',
    employment_type: 'FULL_TIME',
    location: 'Office',
    phone: '',
  })
  createError.value = ''
  createdEmployee.value = null
  copiedCredential.value = ''
}

function setAddEmployeeOpen(open: boolean) {
  addEmployeeOpen.value = open
  if (!open) resetCreateForm()
}

async function loadEmployees(showLoading = true) {
  if (showLoading) loading.value = true
  error.value = ''
  try {
    employees.value = await api<EmployeeSummary[]>('/api/employees')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load people.'
  } finally {
    if (showLoading) loading.value = false
  }
}

async function createEmployee() {
  creating.value = true
  createError.value = ''
  try {
    createdEmployee.value = await api<EmployeeCreateResult>('/api/employees', {
      method: 'POST',
      body: JSON.stringify({
        ...newEmployee,
        phone: newEmployee.phone || null,
      }),
    })
    await loadEmployees(false)
  } catch (err) {
    createError.value = err instanceof Error ? err.message : 'Could not add employee.'
  } finally {
    creating.value = false
  }
}

async function copyCredential(value: string, kind: 'login' | 'password' | 'all') {
  try {
    await navigator.clipboard.writeText(value)
    copiedCredential.value = kind
  } catch {
    copiedCredential.value = ''
  }
}

watch([query, departmentFilter, statusFilter, sortBy], () => {
  page.value = 1
})

onMounted(() => void loadEmployees())
</script>

<template>
  <section class="sheet people-sheet" aria-labelledby="people-directory-title">
    <div class="directory-toolbar">
      <label class="search-field">
        Search people
        <div class="search-control">
          <SearchIcon class="search-icon" :stroke-width="1.8" aria-hidden="true" />
          <Input
            id="people-search"
            v-model="query"
            type="search"
            placeholder="Name, code, email, or location"
            autocomplete="off"
          />
        </div>
      </label>
      <label class="filter-field">
        Department
        <NativeSelect v-model="departmentFilter" class="w-full">
          <NativeSelectOption value="all">All departments</NativeSelectOption>
          <NativeSelectOption
            v-for="department in departments"
            :key="department"
            :value="department"
          >
            {{ department }}
          </NativeSelectOption>
        </NativeSelect>
      </label>
      <label class="filter-field filter-field-short">
        Status
        <NativeSelect v-model="statusFilter" class="w-full">
          <NativeSelectOption value="all">All statuses</NativeSelectOption>
          <NativeSelectOption value="ACTIVE">Active</NativeSelectOption>
          <NativeSelectOption value="INVITED">Invited</NativeSelectOption>
          <NativeSelectOption value="INACTIVE">Inactive</NativeSelectOption>
        </NativeSelect>
      </label>
      <label class="filter-field filter-field-short">
        Sort
        <NativeSelect v-model="sortBy" class="w-full">
          <NativeSelectOption value="name">Name</NativeSelectOption>
          <NativeSelectOption value="code">Employee code</NativeSelectOption>
          <NativeSelectOption value="department">Department</NativeSelectOption>
        </NativeSelect>
      </label>
    </div>

    <div class="directory-meta">
      <div>
        <h1 id="people-directory-title">Employee directory</h1>
        <p v-if="!loading && !error">
          {{ visible.length }} {{ visible.length === 1 ? 'employee' : 'employees' }}
          <span v-if="filtersActive">found</span>
        </p>
      </div>
      <div class="flex gap-2">
        <Button v-if="filtersActive" type="button" variant="ghost" size="sm" @click="clearFilters">
          Clear filters
        </Button>
        <Button type="button" size="sm" @click="setAddEmployeeOpen(true)">
          <PlusIcon aria-hidden="true" />
          Add employee
        </Button>
      </div>
    </div>

    <div v-if="loading" class="state-row" role="status">
      <span class="loading-dot" aria-hidden="true"></span>
      Loading people…
    </div>
    <p v-else-if="error" class="feedback-error" role="alert">{{ error }}</p>
    <EmptyState
      v-else-if="employees.length === 0"
      title="No employees"
      body="Employee records will appear here after HR adds them."
    >
      <UsersRoundIcon class="mx-auto mt-3 size-5 text-[#495057]" aria-hidden="true" />
    </EmptyState>
    <EmptyState
      v-else-if="visible.length === 0"
      title="No results"
      body="No people match this filter. Try another name, department, or status."
    >
      <Button type="button" variant="outline" class="mt-3" @click="clearFilters"
        >Clear filters</Button
      >
    </EmptyState>
    <template v-else>
      <div class="desktop-directory">
        <Table>
          <TableCaption class="sr-only">Employee directory</TableCaption>
          <TableHeader class="sticky top-0 bg-white">
            <TableRow>
              <TableHead>Employee</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Department</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead><span class="sr-only">Open profile</span></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="person in pagedEmployees"
              :key="person.id"
              class="employee-row cursor-pointer"
              tabindex="0"
              :aria-label="`Open ${person.first_name} ${person.last_name}'s profile`"
              @click="openProfile(person)"
              @keydown.enter="openProfile(person)"
              @keydown.space.prevent="openProfile(person)"
            >
              <TableCell>
                <div class="employee-cell">
                  <span class="avatar" aria-hidden="true">{{ initials(person) }}</span>
                  <span>
                    <RouterLink class="employee-name" :to="`/employees/${person.id}`" @click.stop>
                      {{ person.first_name }} {{ person.last_name }}
                    </RouterLink>
                    <span class="employee-code">{{ person.employee_code }}</span>
                  </span>
                </div>
              </TableCell>
              <TableCell>{{ person.title ?? 'Not set' }}</TableCell>
              <TableCell>{{ person.department ?? 'Not set' }}</TableCell>
              <TableCell>{{ roleLabel(person) }}</TableCell>
              <TableCell>
                <StatusBadge
                  :label="employeeStatusLabel(person.status)"
                  :tone="statusTone(employeeStatusLabel(person.status))"
                />
              </TableCell>
              <TableCell class="w-10 text-right">
                <ChevronRightIcon class="ml-auto size-4 text-[#495057]" aria-hidden="true" />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>

      <div class="mobile-directory" aria-label="Employee directory">
        <RouterLink
          v-for="person in pagedEmployees"
          :key="person.id"
          class="mobile-employee"
          :to="`/employees/${person.id}`"
        >
          <span class="avatar" aria-hidden="true">{{ initials(person) }}</span>
          <span class="mobile-employee-copy">
            <strong>{{ person.first_name }} {{ person.last_name }}</strong>
            <span>{{ person.title ?? person.employee_code }}</span>
            <span>{{ person.department ?? 'Department not set' }}</span>
          </span>
          <StatusBadge
            :label="employeeStatusLabel(person.status)"
            :tone="statusTone(employeeStatusLabel(person.status))"
          />
          <ChevronRightIcon class="size-4" aria-hidden="true" />
        </RouterLink>
      </div>

      <footer class="directory-footer">
        <p>Showing {{ rangeStart }}–{{ rangeEnd }} of {{ visible.length }}</p>
        <div class="flex gap-2">
          <Button type="button" size="sm" variant="outline" :disabled="page === 1" @click="page--">
            Previous
          </Button>
          <span class="page-number" aria-live="polite">{{ page }} / {{ pageCount }}</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            :disabled="page === pageCount"
            @click="page++"
          >
            Next
          </Button>
        </div>
      </footer>
    </template>

    <Dialog :open="addEmployeeOpen" @update:open="setAddEmployeeOpen">
      <DialogContent class="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{{ createdEmployee ? 'Employee created' : 'Add employee' }}</DialogTitle>
          <DialogDescription>
            {{
              createdEmployee
                ? 'Share these one-time credentials through your approved company channel.'
                : 'Dayflow generates the login ID and temporary password.'
            }}
          </DialogDescription>
        </DialogHeader>

        <div v-if="createdEmployee" class="grid gap-3">
          <label class="grid gap-1 text-sm">
            Login ID
            <div class="flex gap-2">
              <Input :model-value="createdEmployee.employee_code" readonly />
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label="Copy login ID"
                @click="copyCredential(createdEmployee.employee_code, 'login')"
              >
                <CheckIcon v-if="copiedCredential === 'login'" aria-hidden="true" />
                <CopyIcon v-else aria-hidden="true" />
              </Button>
            </div>
          </label>
          <label class="grid gap-1 text-sm">
            Temporary password
            <div class="flex gap-2">
              <Input :model-value="createdEmployee.initial_password" readonly />
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label="Copy temporary password"
                @click="copyCredential(createdEmployee.initial_password, 'password')"
              >
                <CheckIcon v-if="copiedCredential === 'password'" aria-hidden="true" />
                <CopyIcon v-else aria-hidden="true" />
              </Button>
            </div>
          </label>
          <Button
            type="button"
            variant="outline"
            @click="
              copyCredential(
                `Login ID: ${createdEmployee.employee_code}\nTemporary password: ${createdEmployee.initial_password}`,
                'all',
              )
            "
          >
            <CheckIcon v-if="copiedCredential === 'all'" aria-hidden="true" />
            <CopyIcon v-else aria-hidden="true" />
            Copy both
          </Button>
        </div>

        <form v-else class="grid gap-3" @submit.prevent="createEmployee">
          <div class="grid grid-cols-2 gap-3">
            <label class="grid gap-1 text-sm"
              >First name<Input v-model="newEmployee.first_name" required
            /></label>
            <label class="grid gap-1 text-sm"
              >Last name<Input v-model="newEmployee.last_name" required
            /></label>
          </div>
          <label class="grid gap-1 text-sm"
            >Work email<Input v-model="newEmployee.email" type="email" required
          /></label>
          <div class="grid grid-cols-2 gap-3">
            <label class="grid gap-1 text-sm">Title<Input v-model="newEmployee.title" /></label>
            <label class="grid gap-1 text-sm"
              >Department<Input v-model="newEmployee.department"
            /></label>
          </div>
          <label class="grid gap-1 text-sm">Location<Input v-model="newEmployee.location" /></label>
          <p v-if="createError" role="alert" class="feedback-error">{{ createError }}</p>
          <DialogFooter :show-close-button="false">
            <Button type="button" variant="outline" @click="setAddEmployeeOpen(false)"
              >Cancel</Button
            >
            <Button type="submit" :disabled="creating">{{
              creating ? 'Creating…' : 'Create employee'
            }}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </section>
</template>

<style scoped>
.people-sheet {
  padding: 0;
}

.directory-toolbar {
  display: grid;
  grid-template-columns: minmax(15rem, 1.8fr) minmax(11rem, 1fr) minmax(9rem, 0.7fr) minmax(
      9rem,
      0.7fr
    );
  gap: 0.75rem;
  padding: 1rem;
  border-bottom: 1px solid #dee2e6;
  background: #f8f9fa;
}

.directory-toolbar label {
  display: grid;
  gap: 0.3rem;
  color: #495057;
  font-size: 13px;
  font-weight: 500;
}

.search-control {
  position: relative;
}

.search-control input {
  padding-left: 2.1rem;
  background: #fff;
}

.search-icon {
  position: absolute;
  top: 50%;
  left: 0.65rem;
  z-index: 1;
  width: 1rem;
  height: 1rem;
  color: #495057;
  transform: translateY(-50%);
  pointer-events: none;
}

.directory-meta {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.1rem 1rem 0.75rem;
}

.directory-meta h1 {
  margin: 0;
  font-size: 21px;
  line-height: 1.35;
}

.directory-meta p,
.directory-footer p {
  margin: 0;
  color: #495057;
  font-size: 13px;
}

.desktop-directory {
  overflow-x: auto;
  border-top: 1px solid #dee2e6;
}

.employee-row:focus-visible {
  outline: 2px solid #017e84;
  outline-offset: -2px;
}

.employee-cell {
  display: flex;
  min-width: 13rem;
  align-items: center;
  gap: 0.7rem;
}

.avatar {
  display: inline-grid;
  width: 2.25rem;
  height: 2.25rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid #ded5dc;
  border-radius: 50%;
  background: #f2edf1;
  color: #714b67;
  font-weight: 700;
}

.employee-name,
.employee-code {
  display: block;
}

.employee-name {
  color: #017e84;
  font-weight: 600;
  text-decoration: none;
  text-underline-offset: 3px;
}

.employee-name:hover {
  text-decoration: underline;
}

.employee-code {
  margin-top: 0.1rem;
  color: #495057;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.directory-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid #dee2e6;
}

.page-number {
  display: inline-grid;
  min-width: 3.25rem;
  place-items: center;
  color: #495057;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.state-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 2rem 1rem;
  color: #495057;
}

.loading-dot {
  width: 0.65rem;
  height: 0.65rem;
  border: 2px solid #c8b8c4;
  border-top-color: #714b67;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.mobile-directory {
  display: none;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 820px) {
  .directory-toolbar {
    grid-template-columns: minmax(0, 1fr) minmax(9rem, 0.65fr);
  }

  .search-field {
    grid-column: 1 / -1;
  }
}

@media (max-width: 639px) {
  .directory-toolbar {
    grid-template-columns: 1fr 1fr;
  }

  .filter-field:first-of-type {
    grid-column: 1 / -1;
  }

  .desktop-directory {
    display: none;
  }

  .mobile-directory {
    display: grid;
    border-top: 1px solid #dee2e6;
  }

  .mobile-employee {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 0.65rem;
    min-height: 4.75rem;
    padding: 0.75rem 1rem;
    color: #212529;
    text-decoration: none;
  }

  .mobile-employee + .mobile-employee {
    border-top: 1px solid #dee2e6;
  }

  .mobile-employee-copy,
  .mobile-employee-copy span {
    display: block;
    min-width: 0;
  }

  .mobile-employee-copy span {
    overflow: hidden;
    color: #495057;
    font-size: 12px;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .directory-footer {
    align-items: flex-start;
  }
}
</style>
