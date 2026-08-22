<script setup lang="ts">
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  BanknoteIcon,
  Building2Icon,
  CalendarDaysIcon,
  Clock3Icon,
  InfoIcon,
  ShieldCheckIcon,
} from '@lucide/vue'

const policies = [
  { label: 'Attendance source', value: 'Server time', icon: Clock3Icon },
  { label: 'Work sessions', value: 'One open session per employee', icon: ShieldCheckIcon },
  { label: 'Workweek', value: 'Monday to Friday', icon: CalendarDaysIcon },
  { label: 'Leave policy', value: 'Paid, sick, and unpaid leave', icon: CalendarDaysIcon },
  {
    label: 'Payroll components',
    value: 'Fixed monthly earnings and deductions',
    icon: BanknoteIcon,
  },
  { label: 'Organization', value: 'Dayflow Demo', icon: Building2Icon },
]
</script>

<template>
  <section class="sheet">
    <PageHeader
      title="Settings"
      description="Leave types, workweek, attendance thresholds, payroll components, company details."
    />
    <div
      class="mb-5 flex max-w-5xl items-start gap-3 border border-border bg-muted/40 p-3 text-sm"
      role="note"
    >
      <InfoIcon class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p class="m-0">
        These organization policies are read-only here. Dayflow uses them for attendance,
        leave, and payroll.
      </p>
    </div>
    <div class="max-w-5xl overflow-x-auto">
      <table class="w-full border-collapse text-left" aria-describedby="settings-policy-caption">
        <caption id="settings-policy-caption" class="sr-only">
          Current organization policy configuration
        </caption>
        <thead>
          <tr class="border-b border-border text-sm">
            <th class="px-3 py-2 font-medium">Area</th>
            <th class="px-3 py-2 font-medium">Current policy</th>
            <th class="px-3 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="policy in policies"
            :key="policy.label"
            class="border-b border-border last:border-0"
          >
            <th scope="row" class="px-3 py-3 font-medium">
              <span class="flex items-center gap-3">
                <component
                  :is="policy.icon"
                  class="size-5 shrink-0"
                  :stroke-width="1.75"
                  aria-hidden="true"
                />
                {{ policy.label }}
              </span>
            </th>
            <td class="px-3 py-3 text-muted-foreground">{{ policy.value }}</td>
            <td class="px-3 py-3"><StatusBadge label="Active" tone="confirmed" /></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
