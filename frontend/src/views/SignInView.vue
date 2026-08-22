<script setup lang="ts">
import {
  BanknoteIcon,
  CalendarDaysIcon,
  Clock3Icon,
  EyeIcon,
  EyeOffIcon,
  LoaderCircleIcon,
} from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, HttpError } from '@/api/client'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const router = useRouter()
const route = useRoute()
const resetToken = computed(() =>
  typeof route.query.reset === 'string' ? route.query.reset.trim() : '',
)
const mode = ref<'sign-in' | 'forgot' | 'reset'>(resetToken.value ? 'reset' : 'sign-in')
const identifier = ref('')
const password = ref('')
const passwordConfirmation = ref('')
const error = ref('')
const errorTitle = ref('')
const status = ref('')
const submitting = ref(false)
const passwordVisible = ref(false)
const isForgotMode = computed(() => mode.value === 'forgot')
const isResetMode = computed(() => mode.value === 'reset')
const heading = computed(() => {
  if (isResetMode.value) return 'Choose a new password'
  if (isForgotMode.value) return 'Reset your password'
  return 'Sign in to Dayflow'
})
const description = computed(() => {
  if (isResetMode.value) return 'Set a new password for your Dayflow account.'
  if (isForgotMode.value) return 'Enter your work email or login ID for reset instructions.'
  return 'Use your work email or the login ID issued by HR.'
})

function clearFeedback() {
  error.value = ''
  errorTitle.value = ''
  status.value = ''
}

function showForgotPassword() {
  clearFeedback()
  password.value = ''
  passwordVisible.value = false
  mode.value = 'forgot'
}

function showSignIn() {
  clearFeedback()
  password.value = ''
  passwordConfirmation.value = ''
  passwordVisible.value = false
  mode.value = 'sign-in'
  if (resetToken.value) void router.replace({ name: 'sign-in' })
}

async function onSignIn() {
  clearFeedback()
  submitting.value = true
  try {
    // The API still names this field `email`; it also accepts the generated login ID.
    await session.signIn(identifier.value.trim(), password.value)
    const next = typeof route.query.next === 'string' ? route.query.next : '/dashboard'
    await router.push(next)
  } catch (err) {
    if (err instanceof HttpError && err.status === 403) {
      errorTitle.value = 'Account unavailable'
      error.value = err.detail
    } else if (err instanceof HttpError) {
      errorTitle.value = 'Sign-in failed'
      error.value = err.detail
    } else {
      errorTitle.value = 'Sign-in failed'
      error.value = 'Dayflow could not sign you in. Check your connection and try again.'
    }
  } finally {
    submitting.value = false
  }
}

async function onForgot() {
  clearFeedback()
  submitting.value = true
  try {
    const payload = await api<{ detail: string }>('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email: identifier.value.trim() }),
    })
    status.value = payload.detail
    mode.value = 'sign-in'
  } catch (err) {
    errorTitle.value = 'Reset failed'
    error.value =
      err instanceof HttpError
        ? err.detail
        : 'Dayflow could not send a reset link. Check your connection and try again.'
  } finally {
    submitting.value = false
  }
}

async function onResetPassword() {
  clearFeedback()
  if (!resetToken.value) {
    errorTitle.value = 'Reset link unavailable'
    error.value = 'Request a new reset link and open it from your email.'
    return
  }
  if (password.value !== passwordConfirmation.value) {
    errorTitle.value = 'Passwords do not match'
    error.value = 'Enter the same password in both fields.'
    return
  }

  submitting.value = true
  try {
    const payload = await api<{ detail: string }>('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token: resetToken.value, password: password.value }),
    })
    password.value = ''
    passwordConfirmation.value = ''
    passwordVisible.value = false
    mode.value = 'sign-in'
    await router.replace({ name: 'sign-in' })
    status.value = payload.detail
  } catch (err) {
    errorTitle.value = 'Password reset failed'
    error.value =
      err instanceof HttpError
        ? err.detail
        : 'Dayflow could not reset your password. Check your connection and try again.'
  } finally {
    submitting.value = false
  }
}

function onSubmit() {
  if (isResetMode.value) return onResetPassword()
  if (isForgotMode.value) return onForgot()
  return onSignIn()
}

watch(resetToken, (token) => {
  if (token) {
    clearFeedback()
    password.value = ''
    passwordConfirmation.value = ''
    mode.value = 'reset'
  } else if (mode.value === 'reset') {
    mode.value = 'sign-in'
  }
})
</script>

<template>
  <main class="auth-page">
    <header class="auth-bar">
      <span class="auth-brand">Dayflow</span>
    </header>

    <div class="auth-stage">
      <section class="auth-sheet" aria-labelledby="auth-title">
        <aside class="auth-context" aria-label="Dayflow features">
          <div>
            <h2>Dayflow</h2>
            <p>HR operations for your workday.</p>
          </div>

          <ul class="feature-list">
            <li>
              <Clock3Icon aria-hidden="true" />
              <span>
                <strong>Attendance</strong>
                <small>Record workdays and review attendance.</small>
              </span>
            </li>
            <li>
              <CalendarDaysIcon aria-hidden="true" />
              <span>
                <strong>Time off</strong>
                <small>Request leave and follow each decision.</small>
              </span>
            </li>
            <li>
              <BanknoteIcon aria-hidden="true" />
              <span>
                <strong>Payroll</strong>
                <small>View pay periods and published payslips.</small>
              </span>
            </li>
          </ul>
        </aside>

        <div class="auth-form-pane">
          <div class="auth-form-wrap">
            <div class="auth-heading">
              <h1 id="auth-title">{{ heading }}</h1>
              <p>{{ description }}</p>
            </div>

            <p v-if="status" class="auth-status" role="status" aria-live="polite">
              {{ status }}
            </p>

            <Alert v-if="error" variant="destructive" class="auth-alert">
              <AlertTitle>{{ errorTitle }}</AlertTitle>
              <AlertDescription>{{ error }}</AlertDescription>
            </Alert>

            <form class="auth-form" @submit.prevent="onSubmit">
              <template v-if="!isResetMode">
                <label class="field-label" for="sign-in-identifier"> Work email or login ID </label>
                <Input
                  id="sign-in-identifier"
                  v-model="identifier"
                  type="text"
                  autocomplete="username"
                  placeholder="name@company.com or EMP-1001"
                  :disabled="submitting"
                  :aria-invalid="Boolean(error)"
                  required
                  autofocus
                  class="auth-input"
                />
              </template>

              <template v-if="!isForgotMode">
                <label class="field-label password-label" for="sign-in-password">
                  {{ isResetMode ? 'New password' : 'Password' }}
                </label>
                <div class="password-field">
                  <Input
                    id="sign-in-password"
                    v-model="password"
                    :type="passwordVisible ? 'text' : 'password'"
                    :autocomplete="isResetMode ? 'new-password' : 'current-password'"
                    :disabled="submitting"
                    :aria-invalid="Boolean(error)"
                    required
                    minlength="12"
                    :autofocus="isResetMode"
                    class="auth-input password-input"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    class="password-toggle"
                    :aria-label="passwordVisible ? 'Hide password' : 'Show password'"
                    :disabled="submitting"
                    @click="passwordVisible = !passwordVisible"
                  >
                    <EyeOffIcon v-if="passwordVisible" aria-hidden="true" />
                    <EyeIcon v-else aria-hidden="true" />
                  </Button>
                </div>
              </template>

              <template v-if="isResetMode">
                <label class="field-label password-label" for="reset-password-confirmation">
                  Confirm new password
                </label>
                <Input
                  id="reset-password-confirmation"
                  v-model="passwordConfirmation"
                  :type="passwordVisible ? 'text' : 'password'"
                  autocomplete="new-password"
                  :disabled="submitting"
                  :aria-invalid="Boolean(error)"
                  required
                  minlength="12"
                  class="auth-input"
                />
                <p class="password-help">Use at least 12 characters.</p>
              </template>

              <Button class="submit-button" type="submit" :disabled="submitting">
                <LoaderCircleIcon v-if="submitting" class="loading-icon" aria-hidden="true" />
                {{
                  submitting
                    ? isResetMode
                      ? 'Updating password…'
                      : isForgotMode
                        ? 'Sending reset link…'
                        : 'Signing in…'
                    : isResetMode
                      ? 'Set new password'
                      : isForgotMode
                        ? 'Send reset link'
                        : 'Sign in'
                }}
              </Button>
            </form>

            <Button
              v-if="!isForgotMode && !isResetMode"
              type="button"
              variant="outline"
              class="secondary-action"
              :disabled="submitting"
              @click="showForgotPassword"
            >
              Forgot password
            </Button>
            <Button
              v-else
              type="button"
              variant="ghost"
              class="secondary-action"
              :disabled="submitting"
              @click="showSignIn"
            >
              Back to sign in
            </Button>

            <p class="access-help">Need access? Contact your HR team for a Dayflow login.</p>
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  background: #f8f9fa;
}

.auth-bar {
  display: flex;
  height: 46px;
  align-items: center;
  border-bottom: 1px solid rgb(0 0 0 / 20%);
  background: #714b67;
  padding: 0 24px;
  color: #fff;
}

.auth-brand {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.auth-stage {
  display: grid;
  min-height: calc(100vh - 46px);
  place-items: center;
  padding: 48px 24px;
}

.auth-sheet {
  display: grid;
  width: min(100%, 1120px);
  grid-template-columns: minmax(300px, 0.82fr) minmax(420px, 1.18fr);
  overflow: hidden;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  background: #fff;
}

.auth-context,
.auth-form-pane {
  padding: clamp(40px, 5vw, 72px);
}

.auth-context {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border-right: 1px solid #dee2e6;
  background: #fbfbfc;
}

.auth-context h2 {
  margin: 0 0 4px;
  font-size: 28px;
  letter-spacing: -0.02em;
}

.auth-context p,
.auth-heading p {
  margin: 0;
  color: #495057;
  font-size: 15px;
}

.feature-list {
  display: grid;
  gap: 28px;
  margin: 56px 0 0;
  padding: 0;
  list-style: none;
}

.feature-list li {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  align-items: start;
  gap: 16px;
}

.feature-list svg {
  width: 24px;
  height: 24px;
  color: #714b67;
  stroke-width: 1.7;
}

.feature-list span {
  display: grid;
  gap: 3px;
}

.feature-list strong {
  font-size: 15px;
  font-weight: 600;
}

.feature-list small {
  color: #495057;
  font-size: 13px;
  line-height: 1.5;
}

.auth-form-pane {
  display: flex;
  align-items: center;
}

.auth-form-wrap {
  width: 100%;
  max-width: 480px;
  margin: 0 auto;
}

.auth-heading {
  margin-bottom: 28px;
}

.auth-heading h1 {
  margin: 0 0 6px;
  font-size: clamp(26px, 3vw, 32px);
  line-height: 1.25;
  letter-spacing: -0.025em;
}

.auth-form {
  display: grid;
}

.field-label {
  margin-bottom: 6px;
  font-size: 14px;
  font-weight: 600;
}

.password-label {
  margin-top: 18px;
}

.auth-input {
  height: 44px;
  border-radius: 4px;
  padding-inline: 12px;
}

.password-field {
  position: relative;
}

.password-input {
  padding-right: 48px;
}

.password-help {
  margin: 6px 0 0;
  color: #495057;
  font-size: 13px;
}

.password-toggle {
  position: absolute;
  top: 1px;
  right: 1px;
  width: 42px;
  height: 42px;
  border-radius: 3px;
  color: #495057;
}

.submit-button,
.secondary-action {
  width: 100%;
  height: 44px;
  margin-top: 22px;
  border-radius: 4px;
}

.secondary-action {
  margin-top: 10px;
}

.auth-alert,
.auth-status {
  margin: 0 0 20px;
}

.auth-status {
  border: 1px solid #7fbe8f;
  border-radius: 4px;
  background: #e8f6ec;
  padding: 10px 12px;
  color: #146c2e;
}

.access-help {
  margin: 24px 0 0;
  color: #495057;
  font-size: 13px;
  text-align: center;
}

.loading-icon {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 760px) {
  .auth-bar {
    padding-inline: 16px;
  }

  .auth-stage {
    display: block;
    padding: 20px 12px;
  }

  .auth-sheet {
    display: block;
    max-width: 560px;
    margin: 0 auto;
  }

  .auth-context {
    display: block;
    border-right: 0;
    border-bottom: 1px solid #dee2e6;
    padding: 24px;
  }

  .auth-context h2 {
    font-size: 22px;
  }

  .feature-list {
    display: none;
  }

  .auth-form-pane {
    padding: 28px 24px 32px;
  }

  .auth-heading {
    margin-bottom: 24px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .loading-icon {
    animation-duration: 1.5s;
  }
}
</style>
