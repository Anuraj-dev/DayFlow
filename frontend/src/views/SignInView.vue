<script setup lang="ts">
import { EyeIcon, EyeOffIcon } from '@lucide/vue'
import { ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, HttpError } from '@/api/client'
import { useSessionStore } from '@/stores/session'

const mode = ref<'sign-in' | 'forgot'>('sign-in')
const email = ref('')
const password = ref('')
const error = ref('')
const errorTitle = ref('')
const status = ref('')
const submitting = ref(false)
const passwordVisible = ref(false)
const session = useSessionStore()
const router = useRouter()
const route = useRoute()

async function onSignIn() {
  error.value = ''
  errorTitle.value = ''
  submitting.value = true
  try {
    await session.signIn(email.value, password.value)
    const next = typeof route.query.next === 'string' ? route.query.next : '/dashboard'
    await router.push(next)
  } catch (err) {
    if (err instanceof HttpError && err.status === 403) {
      errorTitle.value = 'Account locked'
      error.value = err.detail
    } else if (err instanceof HttpError) {
      errorTitle.value = 'Sign-in failed'
      error.value = err.detail
    } else {
      errorTitle.value = 'Sign-in failed'
      error.value = 'Could not sign in.'
    }
  } finally {
    submitting.value = false
  }
}

async function onForgot() {
  error.value = ''
  errorTitle.value = ''
  submitting.value = true
  try {
    const payload = await api<{ detail: string }>('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email: email.value }),
    })
    status.value = payload.detail
    mode.value = 'sign-in'
  } catch (err) {
    errorTitle.value = 'Reset failed'
    error.value = err instanceof HttpError ? err.detail : 'Could not send a reset link.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="flex min-h-screen items-center justify-center bg-[#F8F9FA] p-6">
    <section class="sheet sheet-auth">
      <p class="m-0 text-sm font-medium text-[#495057]">Dayflow</p>
      <h1 class="mt-1 mb-4">
        {{ mode === 'forgot' ? 'Reset your password' : 'Sign in with your work email' }}
      </h1>
      <p v-if="status" class="mb-3" role="status">{{ status }}</p>
      <Alert v-if="error" variant="destructive" class="mb-3">
        <AlertTitle>{{ errorTitle }}</AlertTitle>
        <AlertDescription>{{ error }}</AlertDescription>
      </Alert>
      <form class="grid gap-3" @submit.prevent="mode === 'forgot' ? onForgot() : onSignIn()">
        <label class="grid gap-1 text-sm font-medium">
          Work email
          <Input v-model="email" type="email" autocomplete="username" required />
        </label>
        <div v-if="mode === 'sign-in'" class="grid gap-1 text-sm font-medium">
          <label for="sign-in-password">Password</label>
          <span class="flex items-center gap-2">
            <Input
              id="sign-in-password"
              v-model="password"
              :type="passwordVisible ? 'text' : 'password'"
              autocomplete="current-password"
              required
              minlength="12"
            />
            <Button
              type="button"
              variant="outline"
              :aria-label="passwordVisible ? 'Hide password' : 'Show password'"
              @click="passwordVisible = !passwordVisible"
            >
              <EyeOffIcon v-if="passwordVisible" class="size-4" aria-hidden="true" />
              <EyeIcon v-else class="size-4" aria-hidden="true" />
              {{ passwordVisible ? 'Hide' : 'Show' }}
            </Button>
          </span>
        </div>
        <Button v-if="mode === 'sign-in'" type="submit" :disabled="submitting">
          {{ submitting ? 'Signing in…' : 'Sign in' }}
        </Button>
        <Button v-else type="submit" :disabled="submitting">Send reset link</Button>
      </form>
      <div class="mt-4 flex flex-wrap gap-3 text-sm">
        <Button v-if="mode === 'sign-in'" type="button" variant="outline" @click="mode = 'forgot'">
          Forgot password
        </Button>
        <Button v-else type="button" variant="ghost" @click="mode = 'sign-in'">Back to sign in</Button>
        <RouterLink class="self-center text-[#017E84] underline" to="/activate-account">
          Activate account
        </RouterLink>
      </div>
    </section>
  </main>
</template>
