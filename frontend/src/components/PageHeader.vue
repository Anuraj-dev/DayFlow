<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <header class="page-header mb-4 flex flex-wrap items-start justify-between gap-3">
    <div class="min-w-0">
      <h1 class="m-0 text-[24px] leading-[1.4] font-bold text-[#212529] sm:text-[28px] sm:leading-[1.5]">
        {{ title }}
      </h1>
      <p v-if="description" class="m-0 mt-1 text-[14px] leading-[1.5] text-[#495057]">
        {{ description }}
      </p>
    </div>
    <div v-if="$slots.default" class="flex flex-wrap items-center gap-2">
      <slot />
    </div>
  </header>
</template>
