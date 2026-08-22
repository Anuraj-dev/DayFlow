<script setup lang="ts">
import { BanIcon, CircleAlertIcon, CircleCheckIcon } from '@lucide/vue'
import { computed } from 'vue'

const props = defineProps<{
  tone?: 'neutral' | 'confirmed' | 'review' | 'danger'
  label: string
}>()

const resolvedTone = computed(() => props.tone ?? 'neutral')

const icon = computed(() => {
  switch (resolvedTone.value) {
    case 'confirmed':
      return CircleCheckIcon
    case 'danger':
      return BanIcon
    default:
      return CircleAlertIcon
  }
})
</script>

<template>
  <span class="badge" :data-tone="resolvedTone">
    <component
      :is="icon"
      class="badge-icon"
      :stroke-width="2"
      aria-hidden="true"
    />
    <span>{{ label }}</span>
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.15rem 0.5rem;
  border: 1px solid #dee2e6;
  border-radius: 3px;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  background: #ffffff;
  color: #212529;
  white-space: nowrap;
}

.badge-icon {
  width: 0.875rem;
  height: 0.875rem;
  flex-shrink: 0;
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

.badge[data-tone='neutral'] {
  background: #ffffff;
  color: #495057;
  border-color: #dee2e6;
}
</style>
