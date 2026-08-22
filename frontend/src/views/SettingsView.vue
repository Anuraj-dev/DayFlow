<script setup lang="ts">
import { CircleAlertIcon } from '@lucide/vue'
import { computed, nextTick, onMounted, ref } from 'vue'

import StatusBadge from '@/components/StatusBadge.vue'
import { Button } from '@/components/ui/button'
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

/** Seeded org policy copy — settings has no live policy API in the prototype. */
const POLICIES = [
  {
    id: 'attendance-source',
    policy: 'Attendance source',
    value: 'Server time',
  },
  {
    id: 'work-sessions',
    policy: 'Work sessions',
    value: 'One open session per employee',
  },
  {
    id: 'workweek',
    policy: 'Workweek',
    value: 'Mon–Fri (Asia/Kolkata)',
  },
  {
    id: 'leave-grants',
    policy: 'Leave grants',
    value: '18 paid / 8 sick days',
  },
  {
    id: 'currency',
    policy: 'Currency',
    value: 'INR',
  },
] as const

const query = ref('')
const controlActionsReady = ref(false)

const visiblePolicies = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return POLICIES
  return POLICIES.filter(
    (row) =>
      row.policy.toLowerCase().includes(q) || row.value.toLowerCase().includes(q),
  )
})

onMounted(async () => {
  await nextTick()
  controlActionsReady.value = Boolean(document.getElementById('control-actions'))
})
</script>

<template>
  <section class="sheet">
    <Teleport v-if="controlActionsReady" defer to="#control-actions">
      <div class="flex w-full min-w-0 flex-wrap items-center gap-2">
        <label class="sr-only" for="settings-policy-search">Search policies</label>
        <Input
          id="settings-policy-search"
          v-model="query"
          type="search"
          class="max-w-xs min-w-48 flex-1"
          placeholder="Search policies…"
          autocomplete="off"
        />
        <Button type="button" disabled title="Policy editing is deferred in the prototype">
          Edit policies
        </Button>
      </div>
    </Teleport>

    <div
      v-if="!controlActionsReady"
      class="mb-3 flex flex-wrap items-center gap-2 border-b border-[#DEE2E6] pb-3"
    >
      <label class="sr-only" for="settings-policy-search-fallback">Search policies</label>
      <Input
        id="settings-policy-search-fallback"
        v-model="query"
        type="search"
        class="max-w-xs min-w-48 flex-1"
        placeholder="Search policies…"
        autocomplete="off"
      />
      <Button type="button" disabled title="Policy editing is deferred in the prototype">
        Edit policies
      </Button>
    </div>

    <div class="settings-sheet">
      <Table>
        <TableCaption class="sr-only">Organization policy sheet</TableCaption>
        <TableHeader class="sticky top-0 bg-white">
          <TableRow>
            <TableHead>Policy</TableHead>
            <TableHead>Value</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="visiblePolicies.length === 0">
            <TableCell colspan="3">No policies match this search.</TableCell>
          </TableRow>
          <TableRow v-for="row in visiblePolicies" :key="row.id">
            <TableCell class="font-medium">{{ row.policy }}</TableCell>
            <TableCell class="text-[#495057]">{{ row.value }}</TableCell>
            <TableCell>
              <StatusBadge label="Active" tone="confirmed" />
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <div class="mobile-policy-list" aria-label="Organization policies">
        <p v-if="visiblePolicies.length === 0" class="m-0 text-[14px] text-[#495057]">
          No policies match this search.
        </p>
        <div v-for="row in visiblePolicies" :key="`m-${row.id}`" class="mobile-policy-row">
          <div class="mobile-policy-copy">
            <strong>{{ row.policy }}</strong>
            <span>{{ row.value }}</span>
          </div>
          <StatusBadge label="Active" tone="confirmed" />
        </div>
      </div>

      <div class="deferred-banner" role="status">
        <CircleAlertIcon class="deferred-icon" :stroke-width="2" aria-hidden="true" />
        <div>
          <p class="deferred-title">Policy editing is deferred</p>
          <p class="deferred-body">
            These policies are read-only in the prototype. Existing attendance, leave, and payroll
            flows continue to use the seeded values. There is no settings edit or audit-log API yet.
          </p>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.settings-sheet {
  display: grid;
  gap: 1rem;
}

.mobile-policy-list {
  display: none;
}

.mobile-policy-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid #dee2e6;
}

.mobile-policy-row:last-of-type {
  border-bottom: none;
}

.mobile-policy-copy {
  display: grid;
  gap: 0.15rem;
  min-width: 0;
}

.mobile-policy-copy strong {
  font-size: 14px;
  font-weight: 700;
  color: #212529;
}

.mobile-policy-copy span {
  font-size: 14px;
  color: #495057;
}

.deferred-banner {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.75rem 0.85rem;
  border: 1px solid var(--warning);
  border-radius: 4px;
  background: var(--warning-bg);
  color: #212529;
}

.deferred-icon {
  width: 1.1rem;
  height: 1.1rem;
  flex-shrink: 0;
  margin-top: 0.1rem;
  color: #7a5200;
}

.deferred-title {
  margin: 0 0 0.2rem;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.4;
}

.deferred-body {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  color: #495057;
}

@media (max-width: 639px) {
  .settings-sheet :deep(table) {
    display: none;
  }

  .mobile-policy-list {
    display: block;
  }
}
</style>
