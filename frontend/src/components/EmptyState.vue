<script setup lang="ts">
import { FileTextIcon } from '@lucide/vue'

defineProps<{
  title: string
  body: string
}>()
</script>

<template>
  <div class="empty" role="status">
    <div class="empty-icon" aria-hidden="true">
      <slot name="icon">
        <FileTextIcon class="size-5" :stroke-width="1.75" />
      </slot>
    </div>
    <h2>{{ title }}</h2>
    <p>{{ body }}</p>
    <div v-if="$slots.default" class="empty-actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty {
  padding: 1.25rem 0;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  margin-bottom: 0.5rem;
  color: #495057;
}

h2 {
  margin: 0 0 0.35rem;
  font-size: 21px;
  font-weight: 700;
  line-height: 1.5;
  color: #212529;
}

p {
  margin: 0;
  color: #495057;
  font-size: 14px;
  line-height: 1.5;
}

.empty-actions {
  margin-top: 0.75rem;
}
</style>
