<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from '@/components/ui/breadcrumb'
import { Input } from '@/components/ui/input'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const router = useRouter()
const route = useRoute()
const menuOpen = ref(false)
const filter = ref('')

const nav = computed(() => {
  const items = [
    { to: '/dashboard', label: 'Overview' },
    { to: '/attendance', label: 'Attendance' },
    { to: '/time-off', label: 'Time off' },
    { to: '/payroll', label: 'Payroll' },
  ]
  if (session.isHr) {
    items.splice(1, 0, { to: '/employees', label: 'People' })
    items.push({ to: '/settings', label: 'Settings' })
  }
  return items
})

const profilePath = computed(() =>
  session.user?.employee_id ? `/employees/${session.user.employee_id}` : '/dashboard',
)

const pageTitle = computed(() => (typeof route.meta.title === 'string' ? route.meta.title : 'Overview'))

async function signOut() {
  session.signOut()
  menuOpen.value = false
  await router.push({ name: 'sign-in' })
}
</script>

<template>
  <div class="flex min-h-screen flex-col bg-background text-[14px]">
    <a
      class="skip sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-3 focus:z-50 focus:bg-white focus:px-3 focus:py-1"
      href="#main"
    >
      Skip to content
    </a>
    <header
      data-slot="app-navbar"
      class="flex h-[46px] w-full items-stretch border-b border-black/20 bg-primary text-white/90"
    >
      <div class="flex items-center px-4 font-bold tracking-wide">Dayflow</div>
      <nav aria-label="Product areas" class="flex flex-1 items-stretch">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="flex items-center px-3 text-white/90 no-underline hover:bg-black/8"
          active-class="bg-black/8 text-white"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="relative flex items-center pr-3">
        <button
          type="button"
          class="h-full px-3 text-white/90 hover:bg-black/8"
          aria-haspopup="menu"
          :aria-expanded="menuOpen"
          @click="menuOpen = !menuOpen"
        >
          {{ session.displayName }}
        </button>
        <div v-if="menuOpen" class="absolute top-full right-2 z-20 min-w-40 border border-border bg-white text-foreground shadow-none" role="menu">
          <RouterLink
            role="menuitem"
            class="block px-3 py-2 no-underline hover:bg-muted"
            :to="profilePath"
            @click="menuOpen = false"
          >
            My profile
          </RouterLink>
          <button type="button" role="menuitem" class="block w-full px-3 py-2 text-left hover:bg-muted" @click="signOut">
            Log out
          </button>
        </div>
      </div>
    </header>
    <div
      data-slot="control-panel"
      class="flex flex-wrap items-center gap-3 border-b border-[#DEE2E6] bg-white px-4 py-2"
    >
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbPage>{{ pageTitle }}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div class="ml-auto flex items-center gap-2">
        <label class="sr-only" for="shell-filter">Search</label>
        <Input id="shell-filter" v-model="filter" type="search" placeholder="Search" class="h-8 w-48 rounded-[4px]" />
        <div id="control-actions" class="flex items-center gap-2" />
      </div>
    </div>
    <main id="main" class="flex-1 bg-[#F8F9FA] p-4">
      <RouterView />
    </main>
  </div>
</template>
