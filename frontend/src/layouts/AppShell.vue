<script setup lang="ts">
import {
  BanknoteIcon,
  CalendarDaysIcon,
  Clock3Icon,
  LayoutDashboardIcon,
  MenuIcon,
  SettingsIcon,
  UsersRoundIcon,
  XIcon,
} from '@lucide/vue'
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'

import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const router = useRouter()
const menuOpen = ref(false)
const mobileNavOpen = ref(false)
const menuWrap = ref<HTMLElement | null>(null)
const accountButton = ref<HTMLButtonElement | null>(null)

const nav = computed(() => {
  const items = [
    { to: '/dashboard', label: 'Overview', icon: LayoutDashboardIcon },
    { to: '/attendance', label: 'Attendance', icon: Clock3Icon },
    { to: '/time-off', label: 'Time off', icon: CalendarDaysIcon },
    { to: '/payroll', label: 'Payroll', icon: BanknoteIcon },
  ]
  if (session.isHr) {
    items.splice(1, 0, { to: '/employees', label: 'People', icon: UsersRoundIcon })
    items.push({ to: '/settings', label: 'Settings', icon: SettingsIcon })
  }
  return items
})

const profilePath = computed(() =>
  session.user?.employee_id ? `/employees/${session.user.employee_id}` : '/dashboard',
)

async function signOut() {
  session.signOut()
  menuOpen.value = false
  mobileNavOpen.value = false
  await router.push({ name: 'sign-in' })
}

function closeMobileNav() {
  mobileNavOpen.value = false
}

async function closeAccountMenu({ restoreFocus = false } = {}) {
  menuOpen.value = false
  if (restoreFocus) {
    await nextTick()
    accountButton.value?.focus()
  }
}

function onDocumentPointer(event: PointerEvent) {
  if (!menuOpen.value) return
  if (menuWrap.value?.contains(event.target as Node)) return
  menuOpen.value = false
}

function onDocumentKey(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    if (menuOpen.value) void closeAccountMenu({ restoreFocus: true })
    mobileNavOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocumentPointer)
  document.addEventListener('keydown', onDocumentKey)
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocumentPointer)
  document.removeEventListener('keydown', onDocumentKey)
})
</script>

<template>
  <div class="flex min-h-screen flex-col bg-background">
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
      <nav aria-label="Product areas" class="hidden min-w-0 flex-1 items-stretch sm:flex">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="relative flex items-center px-3 text-white/90 no-underline hover:bg-black/8"
          active-class="bg-black/12 text-white after:absolute after:right-3 after:bottom-0 after:left-3 after:h-0.5 after:bg-white"
        >
          <component
            :is="item.icon"
            class="mr-2 size-4 shrink-0"
            :stroke-width="1.75"
            aria-hidden="true"
          />
          {{ item.label }}
        </RouterLink>
      </nav>
      <button
        type="button"
        class="ml-auto flex size-[46px] items-center justify-center text-white sm:hidden"
        :aria-expanded="mobileNavOpen"
        aria-controls="mobile-product-nav"
        aria-label="Toggle navigation"
        @click="mobileNavOpen = !mobileNavOpen"
      >
        <XIcon v-if="mobileNavOpen" class="size-5" aria-hidden="true" />
        <MenuIcon v-else class="size-5" aria-hidden="true" />
      </button>
      <div ref="menuWrap" class="relative hidden items-center pr-3 sm:flex">
        <button
          ref="accountButton"
          type="button"
          class="h-full px-3 text-white/90 hover:bg-black/8"
          aria-haspopup="menu"
          aria-controls="account-menu"
          :aria-expanded="menuOpen"
          @click="menuOpen = !menuOpen"
        >
          {{ session.displayName }}
        </button>
        <div
          v-if="menuOpen"
          id="account-menu"
          class="absolute top-full right-2 z-20 min-w-40 border border-border bg-white text-foreground shadow-none"
          role="menu"
        >
          <RouterLink
            role="menuitem"
            class="block px-3 py-2 no-underline hover:bg-muted"
            :to="profilePath"
            @click="closeAccountMenu()"
          >
            My profile
          </RouterLink>
          <button
            type="button"
            role="menuitem"
            class="block w-full px-3 py-2 text-left hover:bg-muted"
            @click="signOut"
          >
            Log out
          </button>
        </div>
      </div>
    </header>
    <nav
      v-if="mobileNavOpen"
      id="mobile-product-nav"
      aria-label="Mobile product areas"
      class="border-b border-black/20 bg-primary text-white sm:hidden"
    >
      <RouterLink
        v-for="item in nav"
        :key="item.to"
        :to="item.to"
        class="flex min-h-[44px] items-center border-t border-white/10 px-4 no-underline"
        active-class="bg-black/12 font-medium"
        @click="closeMobileNav"
      >
        <component
          :is="item.icon"
          class="mr-3 size-4 shrink-0"
          :stroke-width="1.75"
          aria-hidden="true"
        />
        {{ item.label }}
      </RouterLink>
      <RouterLink
        :to="profilePath"
        class="flex min-h-[44px] items-center border-t border-white/10 px-4 no-underline"
        @click="closeMobileNav"
      >
        My profile
      </RouterLink>
      <button
        type="button"
        class="flex min-h-[44px] w-full items-center border-t border-white/10 px-4 text-left"
        @click="signOut"
      >
        Log out
      </button>
    </nav>
    <div
      data-slot="control-panel"
      class="flex min-w-0 flex-wrap items-center gap-3 border-b border-[#DEE2E6] bg-white px-4 py-2 has-[#control-actions:empty]:hidden"
    >
      <div
        id="control-actions"
        class="flex w-full flex-wrap items-center gap-2 sm:ml-auto sm:w-auto"
      />
    </div>
    <main id="main" class="min-w-0 flex-1 bg-[#F8F9FA] p-3 sm:p-4">
      <RouterView />
    </main>
  </div>
</template>
