<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <header class="mb-4 flex flex-wrap items-start justify-between gap-3">
    <div>
      <h1 class="m-0 text-[28px] leading-[1.5] font-bold">{{ title }}</h1>
      <p v-if="description" class="m-0 text-[#495057]">{{ description }}</p>
    </div>
    <div class="flex gap-2">
      <slot />
    </div>
  </header>
</template>
