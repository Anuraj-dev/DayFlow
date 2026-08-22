import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api, setToken } from '@/api/client'
import type { Role, SessionUser, SignInResponse } from '@/types/domain'

export const useSessionStore = defineStore('session', () => {
  const user = ref<SessionUser | null>(null)

  const role = computed<Role | null>(() => user.value?.role ?? null)
  const isHr = computed(() => role.value === 'HR')
  const displayName = computed(() => {
    if (!user.value) return ''
    const name = [user.value.first_name, user.value.last_name].filter(Boolean).join(' ')
    return name || user.value.email
  })

  async function hydrate(): Promise<void> {
    try {
      user.value = await api<SessionUser>('/api/auth/me')
    } catch {
      user.value = null
      setToken(null)
    }
  }

  async function signIn(email: string, password: string): Promise<void> {
    const payload = await api<SignInResponse>('/api/auth/sign-in', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    setToken(payload.access_token)
    user.value = payload.user
  }

  function signOut(): void {
    setToken(null)
    user.value = null
  }

  return { user, role, isHr, displayName, hydrate, signIn, signOut }
})
