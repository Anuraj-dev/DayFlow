<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
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
import { api, HttpError } from '@/api/client'
import { employeeStatusLabel, presenceLabel, statusTone } from '@/lib/status'
import { useSessionStore } from '@/stores/session'
import type { EmployeeStatus, EmployeeSummary } from '@/types/domain'

const session = useSessionStore()
const employees = ref<EmployeeSummary[]>([])
const loading = ref(true)
const error = ref('')
const query = ref('')
const statusFilter = ref<'all' | EmployeeStatus>('all')
const sortBy = ref<'name' | 'code' | 'department'>('name')
const page = ref(1)
const PAGE_SIZE = 20
const hireOpen = ref(false)
const hiring = ref(false)
const hireError = ref('')
const inviteToken = ref('')
const inviteCode = ref('')
const hire = reactive({
  first_name: '',
  last_name: '',
  email: '',
  title: '',
  department: '',
  joined_on: '',
})

const visible = computed(() => {
  const term = query.value.trim().toLowerCase()
  return employees.value.filter((row) => {
    if (statusFilter.value !== 'all' && row.status !== statusFilter.value) return false
    if (!term) return true
    return `${row.employee_code} ${row.first_name} ${row.last_name} ${row.role ?? ''} ${row.title ?? ''} ${row.department ?? ''}`
      .toLowerCase()
      .includes(term)
  }).sort((a, b) => {
    if (sortBy.value === 'code') return a.employee_code.localeCompare(b.employee_code)
    if (sortBy.value === 'department') return (a.department ?? '').localeCompare(b.department ?? '')
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

function clearFilters() {
  query.value = ''
  statusFilter.value = 'all'
  sortBy.value = 'name'
}

watch([query, statusFilter, sortBy], () => {
  page.value = 1
})

async function loadPeople() {
  employees.value = await api('/api/employees')
}

onMounted(async () => {
  try {
    await loadPeople()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load people.'
  } finally {
    loading.value = false
  }
})

function openHire() {
  hireError.value = ''
  inviteToken.value = ''
  inviteCode.value = ''
  hire.first_name = ''
  hire.last_name = ''
  hire.email = ''
  hire.title = ''
  hire.department = ''
  hire.joined_on = ''
  hireOpen.value = true
}

async function submitHire() {
  hireError.value = ''
  hiring.value = true
  try {
    const payload = await api<{
      employee: EmployeeSummary
      invite_token: string
      employee_code: string
    }>('/api/employees', {
      method: 'POST',
      body: JSON.stringify({
        first_name: hire.first_name,
        last_name: hire.last_name,
        email: hire.email,
        title: hire.title || null,
        department: hire.department || null,
        joined_on: hire.joined_on || null,
      }),
    })
    inviteToken.value = payload.invite_token
    inviteCode.value = payload.employee_code
    await loadPeople()
  } catch (err) {
    hireError.value = err instanceof HttpError ? err.detail : 'Could not create this employee.'
  } finally {
    hiring.value = false
  }
}
</script>

<template>
  <section class="sheet">
    <PageHeader title="People" description="Find, activate, and open employee records.">
      <Button v-if="session.isHr" type="button" @click="openHire">New</Button>
    </PageHeader>
    <div class="mb-3 flex flex-wrap gap-3">
      <label class="grid max-w-xs min-w-48 flex-1 gap-1 text-sm font-medium">
        Filter people
        <Input v-model="query" type="search" />
      </label>
      <label class="grid w-40 gap-1 text-sm font-medium">
        Status
        <NativeSelect v-model="statusFilter" class="w-full">
          <NativeSelectOption value="all">All</NativeSelectOption>
          <NativeSelectOption value="ACTIVE">Active</NativeSelectOption>
          <NativeSelectOption value="INVITED">Invited</NativeSelectOption>
          <NativeSelectOption value="INACTIVE">Inactive</NativeSelectOption>
        </NativeSelect>
      </label>
      <label class="grid w-44 gap-1 text-sm font-medium">
        Sort by
        <NativeSelect v-model="sortBy" class="w-full">
          <NativeSelectOption value="name">Name</NativeSelectOption>
          <NativeSelectOption value="code">Employee code</NativeSelectOption>
          <NativeSelectOption value="department">Department</NativeSelectOption>
        </NativeSelect>
      </label>
    </div>
    <p v-if="loading">Loading people…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <EmptyState
      v-else-if="employees.length === 0"
      title="No employees"
      body="HR can add or import people, then send an invite."
    />
    <EmptyState
      v-else-if="visible.length === 0"
      title="No results"
      body="No people match this filter."
    >
      <Button type="button" variant="outline" class="mt-3" @click="clearFilters">Clear filters</Button>
    </EmptyState>
    <template v-else>
      <div class="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm text-[#495057]">
        <p class="m-0">Showing {{ rangeStart }}–{{ rangeEnd }} of {{ visible.length }} people</p>
        <div class="flex gap-2">
          <Button type="button" size="sm" variant="outline" :disabled="page === 1" @click="page--">Previous</Button>
          <Button type="button" size="sm" variant="outline" :disabled="page === pageCount" @click="page++">Next</Button>
        </div>
      </div>
      <Table>
      <TableCaption class="sr-only">Employee directory</TableCaption>
      <TableHeader class="sticky top-0 bg-white">
        <TableRow>
          <TableHead>Code</TableHead>
          <TableHead>Name</TableHead>
          <TableHead>Title</TableHead>
          <TableHead>Department</TableHead>
          <TableHead>Role</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Attendance</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-for="person in pagedEmployees" :key="person.id">
          <TableCell>
            <RouterLink class="text-[#017E84] underline" :to="`/employees/${person.id}`">
              {{ person.employee_code }}
            </RouterLink>
          </TableCell>
          <TableCell>
            <RouterLink class="font-medium text-[#017E84] underline" :to="`/employees/${person.id}`">
              {{ person.first_name }} {{ person.last_name }}
            </RouterLink>
          </TableCell>
          <TableCell>{{ person.title ?? '—' }}</TableCell>
          <TableCell>{{ person.department ?? '—' }}</TableCell>
          <TableCell>{{ person.role ?? '—' }}</TableCell>
          <TableCell>
            <StatusBadge
              :label="employeeStatusLabel(person.status)"
              :tone="statusTone(employeeStatusLabel(person.status))"
            />
          </TableCell>
          <TableCell>
            <StatusBadge
              :label="presenceLabel(person.presence)"
              :tone="statusTone(presenceLabel(person.presence))"
            />
          </TableCell>
        </TableRow>
      </TableBody>
      </Table>
    </template>
    <Dialog :open="hireOpen" @update:open="hireOpen = $event">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New employee</DialogTitle>
          <DialogDescription>
            Creates an invited record and a one-time activate token.
          </DialogDescription>
        </DialogHeader>
        <p v-if="hireError" role="alert">{{ hireError }}</p>
        <p v-if="inviteToken" role="status">
          Code {{ inviteCode }}. Invite token: {{ inviteToken }}. Share these so they can activate.
        </p>
        <form v-else class="grid gap-3" @submit.prevent="submitHire">
          <label class="grid gap-1 text-sm font-medium">
            First name
            <Input v-model="hire.first_name" required />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Last name
            <Input v-model="hire.last_name" required />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Work email
            <Input v-model="hire.email" type="email" required />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Title
            <Input v-model="hire.title" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Department
            <Input v-model="hire.department" />
          </label>
          <label class="grid gap-1 text-sm font-medium">
            Joined on
            <Input v-model="hire.joined_on" type="date" />
          </label>
          <DialogFooter>
            <Button type="submit" :disabled="hiring">{{ hiring ? 'Creating…' : 'Create' }}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  </section>
</template>
