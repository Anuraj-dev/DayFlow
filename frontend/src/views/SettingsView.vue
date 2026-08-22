<script setup lang="ts">
import EmptyState from '@/components/EmptyState.vue'
import PageHeader from '@/components/PageHeader.vue'
</script>

<template>
  <section class="sheet">
    <PageHeader
      title="Settings"
      description="Leave types, workweek, attendance thresholds, payroll components, company details."
    />
    <EmptyState
      title="Policies are seeded"
      body="The settings UI is deferred for the prototype. Change seed values in the backend until this page is built."
    />
  </section>
</template>
