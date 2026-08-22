<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
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

const visible = computed(() => {
  const term = query.value.trim().toLowerCase()
  return employees.value.filter((row) => {
    if (statusFilter.value !== 'all' && row.status !== statusFilter.value) return false
    if (!term) return true
    return `${row.employee_code} ${row.first_name} ${row.last_name} ${row.role ?? ''} ${row.title ?? ''} ${row.department ?? ''}`
      .toLowerCase()
      .includes(term)
  })
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
    <PageHeader title="People" description="Find, activate, and open employee records." />
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
    />
    <Table v-else>
      <TableCaption class="sr-only">Employee directory</TableCaption>
      <TableHeader>
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
        <TableRow v-for="person in visible" :key="person.id">
          <TableCell>
            <RouterLink class="text-[#017E84] underline" :to="`/employees/${person.id}`">
              {{ person.employee_code }}
            </RouterLink>
          </TableCell>
          <TableCell>{{ person.first_name }} {{ person.last_name }}</TableCell>
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
  </section>
</template>
