<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, HttpError } from '@/api/client'

const route = useRoute()
const employeeCode = ref('')
const email = ref('')
const token = ref('')
const password = ref('')
const submitting = ref(false)
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
    if (err instanceof HttpError && err.status === 410) {
      state.value = 'expired'
      detail.value = err.detail
    } else if (err instanceof HttpError && err.status === 409) {
      state.value = 'used'
      detail.value = err.detail
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
    <section class="sheet w-full max-w-md">
      <h1 class="mt-0 mb-2">Activate account</h1>
      <p class="mt-0 mb-4 text-[#495057]">
        Match your invite to employee ID and work email, then set a password.
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
          <Input v-model="employeeCode" required />
        </label>
        <label class="grid gap-1 text-sm font-medium">
          Work email
          <Input v-model="email" type="email" required />
        </label>
        <label class="grid gap-1 text-sm font-medium">
          Invite token
          <Input v-model="token" required />
        </label>
        <label class="grid gap-1 text-sm font-medium">
          New password
          <Input v-model="password" type="password" minlength="12" required />
        </label>
        <Button type="submit" :disabled="submitting">{{ submitting ? 'Activating…' : 'Activate' }}</Button>
      </form>
      <RouterLink class="mt-4 inline-block text-[#017E84] underline" to="/sign-in">Sign in</RouterLink>
    </section>
  </main>
</template>
