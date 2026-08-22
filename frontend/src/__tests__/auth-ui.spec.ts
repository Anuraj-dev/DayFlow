import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import SignInView from '@/views/SignInView.vue'

type FetchMock = ReturnType<typeof vi.fn>

const dashboardStub = defineComponent({
  setup: () => () => h('p', 'Dashboard'),
})

function jsonResponse(status: number, body: unknown): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

function inputByLabel(wrapper: VueWrapper, labelText: string) {
  const label = wrapper.findAll('label').find((node) => node.text().includes(labelText))
  expect(label, `missing label "${labelText}"`).toBeTruthy()
  const controlId = label!.attributes('for')
  return controlId ? wrapper.get(`#${controlId}`) : label!.get('input')
}

function namedButton(wrapper: VueWrapper, text: string) {
  const button = wrapper.findAll('button').find((node) => node.text().includes(text))
  expect(button, `missing button "${text}"`).toBeTruthy()
  return button!
}

async function makeRouter(path: string, query?: Record<string, string>): Promise<Router> {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/sign-in', name: 'sign-in', component: SignInView },
      { path: '/dashboard', name: 'dashboard', component: dashboardStub },
    ],
  })
  await router.push({ path, query })
  await router.isReady()
  return router
}

async function mountView(path = '/sign-in', query?: Record<string, string>) {
  const router = await makeRouter(path, query)
  const wrapper = mount(SignInView, {
    global: {
      plugins: [createPinia(), router],
    },
  })
  return { wrapper, router }
}

describe('SignInView', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn(() => Promise.reject(new Error('Unexpected fetch')))
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
  })

  it('accepts a work email or login ID without showing activation', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.get('h1').text()).toMatch(/Sign in to Dayflow/i)
    expect(inputByLabel(wrapper, 'Work email or login ID').attributes('type')).toBe('text')
    expect(inputByLabel(wrapper, 'Password').attributes('type')).toBe('password')
    expect(namedButton(wrapper, 'Sign in').attributes('disabled')).toBeUndefined()
    expect(namedButton(wrapper, 'Forgot password').exists()).toBe(true)
    expect(wrapper.text()).not.toMatch(/Activate account/i)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('toggles password visibility with an accessible control', async () => {
    const { wrapper } = await mountView()
    const toggle = wrapper.get('button[aria-label="Show password"]')

    await toggle.trigger('click')

    expect(inputByLabel(wrapper, 'Password').attributes('type')).toBe('text')
    expect(wrapper.get('button[aria-label="Hide password"]').element).toBeTruthy()
  })

  it('shows a bad-credentials alert after a 401 from /api/auth/sign-in', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      expect(String(input)).toContain('/api/auth/sign-in')
      return jsonResponse(401, { detail: 'Bad credentials.' })
    })

    const { wrapper } = await mountView()
    await inputByLabel(wrapper, 'Work email or login ID').setValue('EMP-1001')
    await inputByLabel(wrapper, 'Password').setValue('WrongPassword1!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toMatch(/Bad credentials/i)
    expect(wrapper.text()).toMatch(/Sign-in failed/i)
  })

  it('shows account-unavailable copy after a 403 from /api/auth/sign-in', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(403, { detail: 'Account is locked or disabled.' }),
    )

    const { wrapper } = await mountView()
    await inputByLabel(wrapper, 'Work email or login ID').setValue('locked@dayflow.demo')
    await inputByLabel(wrapper, 'Password').setValue('ChangeMe_HR12!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toMatch(/locked or disabled/i)
    expect(wrapper.text()).toMatch(/Account unavailable/i)
  })

  it('submits forgot-password with a work email or login ID and returns to sign in', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toContain('/api/auth/forgot-password')
      expect(init?.method).toBe('POST')
      expect(JSON.parse(String(init?.body))).toEqual({ email: 'hr@dayflow.demo' })
      return jsonResponse(200, { detail: 'If that email is on file, a reset link was sent.' })
    })

    const { wrapper } = await mountView()
    await namedButton(wrapper, 'Forgot password').trigger('click')

    expect(wrapper.get('h1').text()).toMatch(/Reset your password/i)
    expect(inputByLabel(wrapper, 'Work email or login ID').attributes('type')).toBe('text')
    await inputByLabel(wrapper, 'Work email or login ID').setValue('hr@dayflow.demo')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="status"]').text()).toMatch(/reset link/i)
    expect(wrapper.get('h1').text()).toMatch(/Sign in to Dayflow/i)
  })

  it('opens a reset-token form on the sign-in route and checks confirmation locally', async () => {
    const { wrapper } = await mountView('/sign-in', { reset: 'reset-token' })

    expect(wrapper.get('h1').text()).toMatch(/Choose a new password/i)
    expect(wrapper.find('#sign-in-identifier').exists()).toBe(false)
    expect(inputByLabel(wrapper, 'New password').attributes('autocomplete')).toBe('new-password')
    expect(inputByLabel(wrapper, 'Confirm new password').attributes('autocomplete')).toBe(
      'new-password',
    )

    await inputByLabel(wrapper, 'New password').setValue('Changed_Reset12!')
    await inputByLabel(wrapper, 'Confirm new password').setValue('Different_Reset12!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(fetchMock).not.toHaveBeenCalled()
    expect(wrapper.get('[role="alert"]').text()).toMatch(/Passwords do not match/i)
  })

  it('resets the password, removes the token from the URL, and returns to sign in', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toContain('/api/auth/reset-password')
      expect(init?.method).toBe('POST')
      expect(JSON.parse(String(init?.body))).toEqual({
        token: 'valid-reset-token',
        password: 'Changed_Reset12!',
      })
      return jsonResponse(200, { detail: 'Password reset. Sign in with your new password.' })
    })

    const { wrapper, router } = await mountView('/sign-in', { reset: 'valid-reset-token' })
    await inputByLabel(wrapper, 'New password').setValue('Changed_Reset12!')
    await inputByLabel(wrapper, 'Confirm new password').setValue('Changed_Reset12!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.query.reset).toBeUndefined()
    expect(wrapper.get('h1').text()).toMatch(/Sign in to Dayflow/i)
    expect(wrapper.get('[role="status"]').text()).toMatch(/Password reset/i)
  })

  it('keeps the reset form available when the token is invalid or expired', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(400, { detail: 'Reset link is invalid or expired. Request a new one.' }),
    )

    const { wrapper } = await mountView('/sign-in', { reset: 'expired-token' })
    await inputByLabel(wrapper, 'New password').setValue('Changed_Reset12!')
    await inputByLabel(wrapper, 'Confirm new password').setValue('Changed_Reset12!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('h1').text()).toMatch(/Choose a new password/i)
    expect(wrapper.get('[role="alert"]').text()).toMatch(/invalid or expired/i)
    expect(namedButton(wrapper, 'Back to sign in').element).toBeTruthy()
  })

  it('signs in with the existing API payload and opens the requested page', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toContain('/api/auth/sign-in')
      expect(init?.method).toBe('POST')
      expect(JSON.parse(String(init?.body))).toEqual({
        email: 'EMP-1001',
        password: 'ChangeMe_HR12!',
      })
      return jsonResponse(200, {
        access_token: 'seed-token',
        token_type: 'bearer',
        user: {
          id: '11111111-1111-1111-1111-111111111111',
          email: 'hr@dayflow.demo',
          role: 'HR',
          organization_id: '22222222-2222-2222-2222-222222222222',
          employee_id: '33333333-3333-3333-3333-333333333333',
          first_name: 'Hari',
          last_name: 'Rao',
          employee_code: 'HR-001',
        },
      })
    })

    const { wrapper, router } = await mountView('/sign-in', { next: '/dashboard' })
    await inputByLabel(wrapper, 'Work email or login ID').setValue(' EMP-1001 ')
    await inputByLabel(wrapper, 'Password').setValue('ChangeMe_HR12!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/dashboard')
    expect(sessionStorage.getItem('dayflow.token')).toBe('seed-token')
  })
})
