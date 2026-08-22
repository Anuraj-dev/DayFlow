<script setup lang="ts">
import { computed, useSlots } from 'vue'

const slots = useSlots()
const hasRail = computed(() => Boolean(slots.rail))
</script>

<template>
  <div class="flex min-h-screen flex-col bg-[#F8F9FA]">
    <a
      class="skip sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-3 focus:z-50 focus:bg-white focus:px-3 focus:py-1"
      href="#auth-main"
    >
      Skip to content
    </a>
    <header
      data-slot="auth-navbar"
      class="flex h-[46px] w-full shrink-0 items-center border-b border-black/20 bg-[#714B67] px-4 text-[14px] font-bold tracking-wide text-white"
    >
      Dayflow
    </header>
    <main
      id="auth-main"
      class="flex min-w-0 flex-1 items-center justify-center p-4 sm:p-6"
    >
      <div
        class="flex w-full min-w-0 items-stretch gap-4 sm:gap-8"
        :class="
          hasRail
            ? 'max-w-5xl flex-col sm:flex-row sm:items-center'
            : 'max-w-md justify-center'
        "
      >
        <aside
          v-if="hasRail"
          class="min-w-0 flex-1 text-[14px] leading-[1.5] text-[#212529] sm:max-w-md"
        >
          <slot name="rail" />
        </aside>
        <section class="sheet sheet-auth mx-auto w-full shrink-0">
          <slot />
        </section>
      </div>
    </main>
  </div>
</template>
