<script setup lang="ts">
import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
</script>

<template>
  <section class="sheet">
    <PageHeader
      title="Settings"
      description="Leave types, workweek, attendance thresholds, payroll components, company details."
    />
    <div class="grid max-w-3xl gap-4">
      <div class="flex items-center justify-between gap-4 border-b border-border pb-3">
        <div>
          <h2 class="m-0">Attendance source</h2>
          <p class="m-0 text-[#495057]">Check-in and check-out use server time.</p>
        </div>
        <StatusBadge label="Active" tone="confirmed" />
      </div>
      <div class="flex items-center justify-between gap-4 border-b border-border pb-3">
        <div>
          <h2 class="m-0">Work sessions</h2>
          <p class="m-0 text-[#495057]">One attendance session per employee and work date.</p>
        </div>
        <StatusBadge label="Active" tone="confirmed" />
      </div>
      <div class="flex items-center justify-between gap-4 border-b border-border pb-3">
        <div>
          <h2 class="m-0">Payroll components</h2>
          <p class="m-0 text-[#495057]">Payroll uses fixed monthly earning and deduction components.</p>
        </div>
        <StatusBadge label="Active" tone="confirmed" />
      </div>
      <EmptyState
        title="Policy editing is not available yet"
        body="These policies are read-only in the prototype. Existing attendance, leave, and payroll flows continue to use them."
      />
    </div>
  </section>
</template>
