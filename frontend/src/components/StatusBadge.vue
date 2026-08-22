<script setup lang="ts">
defineProps<{
  tone?: 'neutral' | 'confirmed' | 'review' | 'danger'
  label: string
}>()
</script>

<template>
  <span class="badge" :data-tone="tone ?? 'neutral'">{{ label }}</span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.15rem 0.5rem;
  border: 1px solid #DEE2E6;
  border-radius: 3px;
  font-size: 13px;
  font-weight: 500;
  background: #FFFFFF;
  color: #212529;
}

.badge[data-tone='confirmed'] {
  background: var(--success-bg);
  color: #146c2e;
  border-color: var(--success);
}

.badge[data-tone='review'] {
  background: var(--warning-bg);
  color: #7a5200;
  border-color: var(--warning);
}

.badge[data-tone='danger'] {
  background: var(--danger-bg);
  color: #a61b29;
  border-color: var(--danger);
}
</style>
