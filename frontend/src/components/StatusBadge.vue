<script setup lang="ts">
import { AlertTriangleIcon, CheckCircle2Icon, CircleIcon, XCircleIcon } from '@lucide/vue'
import { computed } from 'vue'

const props = defineProps<{
  tone?: 'neutral' | 'confirmed' | 'review' | 'danger'
  label: string
}>()

const icon = computed(() => {
  if (props.tone === 'confirmed') return CheckCircle2Icon
  if (props.tone === 'review') return AlertTriangleIcon
  if (props.tone === 'danger') return XCircleIcon
  return CircleIcon
})
</script>

<template>
  <span class="badge" :data-tone="tone ?? 'neutral'">
    <component :is="icon" class="badge-icon" :stroke-width="2" aria-hidden="true" />
    {{ label }}
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.15rem 0.5rem;
  border: 1px solid #DEE2E6;
  border-radius: 3px;
  font-size: 13px;
  font-weight: 500;
  background: #FFFFFF;
  color: #212529;
}

.badge-icon {
  width: 0.9rem;
  height: 0.9rem;
  flex: none;
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
