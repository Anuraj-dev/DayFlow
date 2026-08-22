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

import { useAttendanceStore } from '@/stores/attendance'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const attendance = useAttendanceStore()
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
  attendance.reset()
  session.signOut()
  menuOpen.value = false
  mobileNavOpen.value = false
  await router.push({ name: 'sign-in' })
}

async function punch(path: '/api/attendance/check-in' | '/api/attendance/check-out') {
  try {
    await attendance.punch(path)
  } catch {
    // Store keeps the API error for the shell alert.
  }
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
  if (session.user?.employee_id) void attendance.load()
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
      <div
        v-if="attendance.visible"
        data-slot="shell-punch"
        class="ml-auto flex min-w-0 max-w-[min(100%,16.5rem)] items-center gap-2 px-2 sm:ml-0 sm:max-w-none sm:px-3"
      >
        <span class="min-w-0 truncate text-[13px] text-white/90" role="status">{{
          attendance.statusLabel
        }}</span>
        <button
          v-if="attendance.canCheckIn"
          type="button"
          class="h-7 shrink-0 border border-white/40 bg-transparent px-2 text-[13px] text-white hover:bg-black/8 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-white"
          :disabled="attendance.punching"
          @click="punch('/api/attendance/check-in')"
        >
          Check in
        </button>
        <button
          v-else-if="attendance.canCheckOut"
          type="button"
          class="h-7 shrink-0 border border-white/40 bg-transparent px-2 text-[13px] text-white hover:bg-black/8 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-white"
          :disabled="attendance.punching"
          @click="punch('/api/attendance/check-out')"
        >
          Check out
        </button>
      </div>
      <button
        type="button"
        class="flex size-[46px] items-center justify-center text-white sm:hidden"
        :class="attendance.visible ? '' : 'ml-auto'"
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
      <div
        v-if="attendance.visible"
        data-slot="shell-punch-mobile"
        class="flex min-h-[44px] items-center justify-between gap-3 border-t border-white/10 px-4"
      >
        <span class="min-w-0 truncate text-[13px] text-white/90" role="status">{{
          attendance.statusLabel
        }}</span>
        <button
          v-if="attendance.canCheckIn"
          type="button"
          class="h-8 shrink-0 border border-white/40 bg-transparent px-2 text-[13px] text-white hover:bg-black/8 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-white"
          :disabled="attendance.punching"
          @click="punch('/api/attendance/check-in')"
        >
          Check in
        </button>
        <button
          v-else-if="attendance.canCheckOut"
          type="button"
          class="h-8 shrink-0 border border-white/40 bg-transparent px-2 text-[13px] text-white hover:bg-black/8 focus-visible:outline focus-visible:outline-offset-2 focus-visible:outline-white"
          :disabled="attendance.punching"
          @click="punch('/api/attendance/check-out')"
        >
          Check out
        </button>
      </div>
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
    <p
      v-if="attendance.visible && (attendance.actionError || attendance.error)"
      data-slot="shell-punch-error"
      class="border-b border-[#DEE2E6] bg-white px-4 py-1 text-[13px] text-[#DC3545]"
      role="alert"
    >
      {{ attendance.actionError || attendance.error }}
    </p>
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
