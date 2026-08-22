<script setup lang="ts">
import { EyeIcon, EyeOffIcon } from '@lucide/vue'
import { ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, HttpError } from '@/api/client'

function classifyActivateError(err: unknown): 'expired' | 'used' | 'other' {
  if (!(err instanceof HttpError)) return 'other'
  const detail = err.detail.toLowerCase()
  if (err.status === 410 || detail.includes('expired')) return 'expired'
  if (
    err.status === 409 ||
    detail.includes('already been used') ||
    detail.includes('already been activated')
  ) {
    return 'used'
  }
  return 'other'
}

const route = useRoute()
const employeeCode = ref('')
const email = ref('')
const token = ref('')
const password = ref('')
const submitting = ref(false)
const passwordVisible = ref(false)
const state = ref<'form' | 'expired' | 'used' | 'sent' | 'verified'>(
  route.query.verified === '1' ? 'verified' : 'form',
)
const detail = ref('')

async function onSubmit() {
  submitting.value = true
  detail.value = ''
  try {
    const payload = await api<{ status?: string; detail?: string }>('/api/auth/activate-account', {
      method: 'POST',
      body: JSON.stringify({
        employee_code: employeeCode.value,
        email: email.value,
        token: token.value,
        password: password.value,
      }),
    })
    state.value = 'sent'
    detail.value = payload.detail || 'Check your work email to verify this account.'
  } catch (err) {
    const classified = classifyActivateError(err)
    if (classified === 'expired' || classified === 'used') {
      state.value = classified
      detail.value = err instanceof HttpError ? err.detail : ''
    } else {
      detail.value = err instanceof HttpError ? err.detail : 'Could not activate this invite.'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="flex min-h-screen items-center justify-center bg-[#F8F9FA] p-6">
    <section class="sheet sheet-auth">
      <h1 class="mt-0 mb-2">Activate account</h1>
      <p class="mt-0 mb-4 text-[#495057]">
        Use the employee ID and invite token from your HR invitation, then set a password.
      </p>
      <Alert v-if="state === 'expired'" variant="destructive" class="mb-3">
        <AlertTitle>Invite expired</AlertTitle>
        <AlertDescription>{{ detail }}</AlertDescription>
      </Alert>
      <Alert v-if="state === 'used'" variant="destructive" class="mb-3">
        <AlertTitle>Already used</AlertTitle>
        <AlertDescription>{{ detail }}</AlertDescription>
      </Alert>
      <p v-else-if="state === 'sent'" role="status">
        Verification sent. {{ detail }} Check your work email.
      </p>
      <p v-else-if="state === 'verified'" role="status">Email verified. You can sign in with your work email.</p>
      <form v-if="state === 'form'" class="grid gap-3" @submit.prevent="onSubmit">
        <Alert v-if="detail" variant="destructive">
          <AlertTitle>Activation failed</AlertTitle>
          <AlertDescription>{{ detail }}</AlertDescription>
        </Alert>
        <label class="grid gap-1 text-sm font-medium">
          Employee ID
          <Input v-model="employeeCode" autocomplete="off" required />
        </label>
        <label class="grid gap-1 text-sm font-medium">
          Work email
          <Input v-model="email" type="email" autocomplete="email" required />
        </label>
        <label class="grid gap-1 text-sm font-medium">
          Invite token
          <Input v-model="token" autocomplete="one-time-code" required />
        </label>
        <div class="grid gap-1 text-sm font-medium">
          <label for="activation-password">New password</label>
          <span class="flex items-center gap-2">
            <Input
              id="activation-password"
              v-model="password"
              :type="passwordVisible ? 'text' : 'password'"
              autocomplete="new-password"
              minlength="12"
              aria-describedby="activation-password-help"
              required
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
          <span id="activation-password-help" class="font-normal text-[#495057]">
            Use at least 12 characters.
          </span>
        </div>
        <Button type="submit" :disabled="submitting">{{ submitting ? 'Activating…' : 'Activate' }}</Button>
      </form>
      <RouterLink class="mt-4 inline-block text-[#017E84] underline" to="/sign-in">Sign in</RouterLink>
    </section>
  </main>
</template>
