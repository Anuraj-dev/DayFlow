<script setup lang="ts">
import {
  BanknoteIcon,
  CalendarDaysIcon,
  ChevronDownIcon,
  Clock3Icon,
  LayoutDashboardIcon,
  MenuIcon,
  SettingsIcon,
  UserRoundIcon,
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
    <header data-slot="app-navbar" class="app-navbar h-[46px] bg-primary">
      <RouterLink class="app-brand" to="/dashboard" aria-label="Dayflow overview">
        Dayflow
      </RouterLink>
      <nav aria-label="Product areas" class="desktop-nav">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          active-class="nav-link-active"
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
        class="mobile-nav-toggle"
        :aria-expanded="mobileNavOpen"
        aria-controls="mobile-product-nav"
        aria-label="Toggle navigation"
        @click="mobileNavOpen = !mobileNavOpen"
      >
        <XIcon v-if="mobileNavOpen" class="size-5" aria-hidden="true" />
        <MenuIcon v-else class="size-5" aria-hidden="true" />
      </button>
      <div ref="menuWrap" class="account-wrap">
        <button
          ref="accountButton"
          type="button"
          class="account-button"
          aria-haspopup="menu"
          aria-controls="account-menu"
          :aria-expanded="menuOpen"
          @click="menuOpen = !menuOpen"
        >
          <UserRoundIcon class="size-4" :stroke-width="1.75" aria-hidden="true" />
          <span>{{ session.displayName }}</span>
          <ChevronDownIcon class="size-3.5" :stroke-width="1.75" aria-hidden="true" />
        </button>
        <div v-if="menuOpen" id="account-menu" class="account-menu" role="menu">
          <RouterLink
            role="menuitem"
            class="account-menu-item"
            :to="profilePath"
            @click="closeAccountMenu()"
          >
            My profile
          </RouterLink>
          <button
            type="button"
            role="menuitem"
            class="account-menu-item w-full text-left"
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
      class="mobile-product-nav border-b border-black/20 bg-primary text-white"
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

<style scoped>
.app-navbar {
  display: grid;
  width: 100%;
  height: 46px;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: stretch;
  border-bottom: 1px solid rgb(0 0 0 / 20%);
  background: #714b67;
  color: rgb(255 255 255 / 90%);
}

.app-brand {
  display: flex;
  width: fit-content;
  align-items: center;
  padding: 0 16px;
  color: #fff;
  font-weight: 700;
  letter-spacing: -0.01em;
  text-decoration: none;
}

.desktop-nav {
  display: flex;
  min-width: 0;
  align-items: stretch;
  justify-content: center;
}

.nav-link {
  position: relative;
  display: flex;
  align-items: center;
  padding: 0 12px;
  color: rgb(255 255 255 / 88%);
  text-decoration: none;
  transition:
    background-color 120ms var(--ease-enter),
    color 120ms var(--ease-enter);
}

.nav-link:hover {
  background: rgb(0 0 0 / 8%);
  color: #fff;
}

.nav-link-active {
  background: rgb(0 0 0 / 12%);
  color: #fff;
}

.nav-link-active::after {
  position: absolute;
  right: 12px;
  bottom: 0;
  left: 12px;
  height: 2px;
  background: #fff;
  content: '';
}

.account-wrap {
  position: relative;
  display: flex;
  min-width: 0;
  align-items: stretch;
  justify-self: end;
  padding-right: 8px;
}

.account-button {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
  padding: 0 10px;
  color: rgb(255 255 255 / 90%);
}

.account-button:hover,
.account-button[aria-expanded='true'] {
  background: rgb(0 0 0 / 8%);
  color: #fff;
}

.account-button span {
  max-width: 170px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-menu {
  position: absolute;
  z-index: 20;
  top: calc(100% + 4px);
  right: 8px;
  min-width: 176px;
  overflow: hidden;
  border: 1px solid #dee2e6;
  border-radius: 4px;
  background: #fff;
  color: #212529;
  box-shadow: 0 8px 18px rgb(33 37 41 / 10%);
}

.account-menu-item {
  display: block;
  min-height: 38px;
  padding: 8px 12px;
  text-decoration: none;
}

.account-menu-item:hover,
.account-menu-item:focus-visible {
  background: #f1f3f5;
}

.mobile-nav-toggle {
  display: none;
  width: 46px;
  height: 46px;
  align-items: center;
  justify-content: center;
  justify-self: end;
  color: #fff;
}

@media (max-width: 1023px) {
  .app-navbar {
    grid-template-columns: auto 1fr auto;
  }

  .desktop-nav,
  .account-wrap {
    display: none;
  }

  .mobile-nav-toggle {
    display: flex;
    grid-column: 3;
  }
}

@media (min-width: 1024px) {
  .mobile-product-nav {
    display: none;
  }
}
</style>
