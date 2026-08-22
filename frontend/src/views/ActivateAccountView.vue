<script setup lang="ts">
import { CircleAlertIcon, CircleCheckIcon, EyeIcon, EyeOffIcon } from '@lucide/vue'
import { computed, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api, HttpError } from '@/api/client'
import AuthFrame from '@/layouts/AuthFrame.vue'

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
const confirmPassword = ref('')
const submitting = ref(false)
const passwordVisible = ref(false)
const confirmVisible = ref(false)
const state = ref<'form' | 'expired' | 'used' | 'sent' | 'verified'>(
  route.query.verified === '1' ? 'verified' : 'form',
)
const detail = ref('')
const mismatch = ref('')

const steps = [
  { id: 1, label: 'Match invite' },
  { id: 2, label: 'Set password' },
  { id: 3, label: 'Verify email' },
] as const

/** Visual only: one POST still covers invite match + password; verify is the sent/verified state. */
const activeStep = computed(() => {
  if (state.value === 'sent' || state.value === 'verified') return 3
  if (state.value === 'form') return 1
  return 1
})

function stepStatus(stepId: number): 'done' | 'current' | 'upcoming' {
  const active = activeStep.value
  if (state.value === 'verified' && stepId <= 3) return 'done'
  if (state.value === 'sent' && stepId < 3) return 'done'
  if (state.value === 'sent' && stepId === 3) return 'current'
  if (stepId < active) return 'done'
  if (stepId === active) return 'current'
  return 'upcoming'
}

async function onSubmit() {
  mismatch.value = ''
  detail.value = ''
  if (password.value !== confirmPassword.value) {
    mismatch.value = 'Confirm password must match.'
    return
  }
  submitting.value = true
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
  <AuthFrame>
    <h1 class="mt-0 mb-2 text-[21px] font-bold leading-[1.5]">Activate account</h1>
    <p class="mt-0 mb-4 text-[14px] text-[#495057]">
      Use the employee ID and invite token from your HR invitation, then set a password.
    </p>

    <ol
      class="mb-5 flex list-none flex-col gap-2 p-0 sm:flex-row sm:items-start sm:gap-0"
      aria-label="Activation steps"
    >
      <li
        v-for="(step, index) in steps"
        :key="step.id"
        class="flex min-w-0 flex-1 items-center gap-2 sm:flex-col sm:items-start sm:gap-1.5"
      >
        <span class="flex items-center gap-2 sm:w-full">
          <span
            class="flex size-6 shrink-0 items-center justify-center rounded-full border text-[12px] font-medium"
            :class="{
              'border-[#714B67] bg-[#714B67] text-white': stepStatus(step.id) === 'current',
              'border-[#28A745] bg-[#28A745] text-white': stepStatus(step.id) === 'done',
              'border-[#DEE2E6] bg-white text-[#495057]': stepStatus(step.id) === 'upcoming',
            }"
            :aria-current="stepStatus(step.id) === 'current' ? 'step' : undefined"
          >
            <CircleCheckIcon
              v-if="stepStatus(step.id) === 'done'"
              class="size-3.5"
              :stroke-width="2.5"
              aria-hidden="true"
            />
            <template v-else>{{ step.id }}</template>
          </span>
          <span
            v-if="index < steps.length - 1"
            class="mx-1 hidden h-px flex-1 bg-[#DEE2E6] sm:block"
            aria-hidden="true"
          />
        </span>
        <span
          class="text-[13px] leading-tight"
          :class="
            stepStatus(step.id) === 'upcoming' ? 'text-[#495057]' : 'font-medium text-[#212529]'
          "
        >
          {{ step.label }}
        </span>
      </li>
    </ol>

    <Alert v-if="state === 'expired'" variant="destructive" class="mb-3">
      <CircleAlertIcon class="size-4" aria-hidden="true" />
      <AlertTitle>Invite expired</AlertTitle>
      <AlertDescription>{{ detail }}</AlertDescription>
    </Alert>
    <Alert v-if="state === 'used'" variant="destructive" class="mb-3">
      <CircleAlertIcon class="size-4" aria-hidden="true" />
      <AlertTitle>Already used</AlertTitle>
      <AlertDescription>{{ detail }}</AlertDescription>
    </Alert>
    <p
      v-else-if="state === 'sent'"
      class="mb-3 flex items-start gap-2 text-[14px] text-[#212529]"
      role="status"
    >
      <CircleCheckIcon class="mt-0.5 size-4 shrink-0 text-[#28A745]" aria-hidden="true" />
      <span>Verification sent. {{ detail }} Check your work email.</span>
    </p>
    <p
      v-else-if="state === 'verified'"
      class="mb-3 flex items-start gap-2 text-[14px] text-[#212529]"
      role="status"
    >
      <CircleCheckIcon class="mt-0.5 size-4 shrink-0 text-[#28A745]" aria-hidden="true" />
      <span>Email verified. You can sign in with your work email.</span>
    </p>

    <form v-if="state === 'form'" class="grid gap-3" @submit.prevent="onSubmit">
      <Alert v-if="detail || mismatch" variant="destructive">
        <CircleAlertIcon class="size-4" aria-hidden="true" />
        <AlertTitle>Activation failed</AlertTitle>
        <AlertDescription>{{ mismatch || detail }}</AlertDescription>
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
      </div>
      <div class="grid gap-1 text-sm font-medium">
        <label for="activation-confirm">Confirm password</label>
        <span class="flex items-center gap-2">
          <Input
            id="activation-confirm"
            v-model="confirmPassword"
            :type="confirmVisible ? 'text' : 'password'"
            autocomplete="new-password"
            minlength="12"
            required
          />
          <Button
            type="button"
            variant="outline"
            :aria-label="confirmVisible ? 'Hide confirm password' : 'Show confirm password'"
            @click="confirmVisible = !confirmVisible"
          >
            <EyeOffIcon v-if="confirmVisible" class="size-4" aria-hidden="true" />
            <EyeIcon v-else class="size-4" aria-hidden="true" />
            {{ confirmVisible ? 'Hide' : 'Show' }}
          </Button>
        </span>
        <span id="activation-password-help" class="font-normal text-[#495057]">
          Use at least 12 characters. Confirm must match.
        </span>
      </div>
      <Button type="submit" :disabled="submitting">{{ submitting ? 'Activating…' : 'Activate' }}</Button>
    </form>
    <RouterLink class="mt-4 inline-block text-[#017E84] underline" to="/sign-in">Sign in</RouterLink>
  </AuthFrame>
</template>
