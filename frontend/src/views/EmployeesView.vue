<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
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
import { api } from '@/api/client'
import { employeeStatusLabel, statusTone } from '@/lib/status'
import type { EmployeeStatus, EmployeeSummary } from '@/types/domain'

const employees = ref<EmployeeSummary[]>([])
const loading = ref(true)
const error = ref('')
const query = ref('')
const statusFilter = ref<'all' | EmployeeStatus>('all')
const sortBy = ref<'name' | 'code' | 'department'>('name')
const page = ref(1)
const PAGE_SIZE = 20

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

onMounted(async () => {
  try {
    employees.value = await api('/api/employees')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Could not load people.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="sheet">
    <PageHeader title="People" description="Find and open employee records." />
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
        </TableRow>
      </TableBody>
      </Table>
    </template>
  </section>
</template>
