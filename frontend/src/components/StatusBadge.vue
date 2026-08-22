<script setup lang="ts">
defineProps<{
  tone?: 'neutral' | 'confirmed' | 'review' | 'danger'
  label: string
}>()
</script>

<template>
  <span class="badge" :data-tone="tone ?? 'neutral'">
    <span class="dot" aria-hidden="true"></span>
    {{ label }}
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.15rem 0.5rem;
  border: 1px solid #DEE2E6;
  border-radius: 3px;
  font-size: 13px;
  font-weight: 500;
  background: #FFFFFF;
  color: #212529;
}

.dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
  background: #495057;
}

.badge[data-tone='confirmed'] {
  background: var(--success-bg);
  color: var(--success);
  border-color: var(--success);
}
.badge[data-tone='confirmed'] .dot {
  background: var(--success);
}

.badge[data-tone='review'] {
  background: var(--warning-bg);
  color: #7a5200;
  border-color: var(--warning);
}
.badge[data-tone='review'] .dot {
  background: var(--warning);
}

.badge[data-tone='danger'] {
  background: var(--danger-bg);
  color: var(--danger);
  border-color: var(--danger);
}
.badge[data-tone='danger'] .dot {
  background: var(--danger);
}
</style>
