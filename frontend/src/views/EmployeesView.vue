<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
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
import { api } from '@/api/client'
import { statusTone } from '@/lib/status'
import type { EmployeeSummary } from '@/types/domain'

const employees = ref<EmployeeSummary[]>([])
const loading = ref(true)
const error = ref('')
const query = ref('')

const visible = computed(() => {
  const term = query.value.trim().toLowerCase()
  if (!term) return employees.value
  return employees.value.filter((person) =>
    `${person.employee_code} ${person.first_name} ${person.last_name} ${person.role ?? ''}`
      .toLowerCase()
      .includes(term),
  )
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
    <label class="mb-3 grid max-w-xs gap-1 text-sm font-medium">
      Filter people
      <Input v-model="query" type="search" />
    </label>
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
          <TableCell>{{ person.role ?? '—' }}</TableCell>
          <TableCell>
            <StatusBadge :label="person.status" :tone="statusTone(person.status)" />
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </section>
</template>
