import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import ActivateAccountView from '@/views/ActivateAccountView.vue'
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
      { path: '/activate-account', name: 'activate-account', component: ActivateAccountView },
      { path: '/dashboard', name: 'dashboard', component: dashboardStub },
    ],
  })
  await router.push({ path, query })
  await router.isReady()
  return router
}

async function mountView(
  component: typeof SignInView | typeof ActivateAccountView,
  path: string,
  query?: Record<string, string>,
) {
  const router = await makeRouter(path, query)
  const wrapper = mount(component, {
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

  it('renders the default sign-in form with forgot-password and activation entry', async () => {
    const { wrapper } = await mountView(SignInView, '/sign-in')

    expect(wrapper.get('h1').text()).toMatch(/Sign in with your work email/i)
    expect(inputByLabel(wrapper, 'Work email').attributes('type')).toBe('email')
    expect(inputByLabel(wrapper, 'Password').attributes('type')).toBe('password')
    expect(namedButton(wrapper, 'Sign in').attributes('disabled')).toBeUndefined()
    expect(namedButton(wrapper, 'Forgot password').exists()).toBe(true)
    expect(wrapper.get('a[href="/activate-account"]').text()).toMatch(/Activate account/i)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('shows a bad-credentials alert after a 401 from /api/auth/sign-in', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      expect(String(input)).toContain('/api/auth/sign-in')
      return jsonResponse(401, { detail: 'Bad credentials.' })
    })

    const { wrapper } = await mountView(SignInView, '/sign-in')
    await inputByLabel(wrapper, 'Work email').setValue('hr@dayflow.demo')
    await inputByLabel(wrapper, 'Password').setValue('WrongPassword1!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toMatch(/Bad credentials/i)
    expect(wrapper.text()).toMatch(/Sign-in failed|Bad credentials/i)
  })

  it('shows locked or disabled copy after a 403 from /api/auth/sign-in', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(403, { detail: 'Account is locked or disabled.' }),
    )

    const { wrapper } = await mountView(SignInView, '/sign-in')
    await inputByLabel(wrapper, 'Work email').setValue('locked@dayflow.demo')
    await inputByLabel(wrapper, 'Password').setValue('ChangeMe_HR12!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const alert = wrapper.get('[role="alert"]')
    expect(alert.text()).toMatch(/locked or disabled/i)
    expect(wrapper.text()).toMatch(/Account locked/i)
  })

  it('submits forgot-password with the work email and shows reset-sent copy', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toContain('/api/auth/forgot-password')
      expect(init?.method).toBe('POST')
      expect(JSON.parse(String(init?.body))).toEqual({ email: 'hr@dayflow.demo' })
      return jsonResponse(200, { detail: 'If that email is on file, a reset link was sent.' })
    })

    const { wrapper } = await mountView(SignInView, '/sign-in')
    await namedButton(wrapper, 'Forgot password').trigger('click')

    expect(wrapper.get('h1').text()).toMatch(/Reset your password/i)
    await inputByLabel(wrapper, 'Work email').setValue('hr@dayflow.demo')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="status"]').text()).toMatch(/reset link/i)
    expect(wrapper.text()).toMatch(/Sign in/i)
  })

  it('signs a seeded account in against /api/auth/sign-in and opens the dashboard', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toContain('/api/auth/sign-in')
      expect(init?.method).toBe('POST')
      expect(JSON.parse(String(init?.body))).toEqual({
        email: 'hr@dayflow.demo',
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

    const { wrapper, router } = await mountView(SignInView, '/sign-in')
    await inputByLabel(wrapper, 'Work email').setValue('hr@dayflow.demo')
    await inputByLabel(wrapper, 'Password').setValue('ChangeMe_HR12!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/dashboard')
    expect(sessionStorage.getItem('dayflow.token')).toBe('seed-token')
  })
})

describe('ActivateAccountView', () => {
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

  async function fillValidInvite(wrapper: VueWrapper) {
    await inputByLabel(wrapper, 'Employee ID').setValue('EMP-1001')
    await inputByLabel(wrapper, 'Work email').setValue('new.hire@dayflow.demo')
    await inputByLabel(wrapper, 'Invite token').setValue('invite-token-1')
    await inputByLabel(wrapper, 'New password').setValue('ChangeMe_Emp12!')
    await inputByLabel(wrapper, 'Confirm password').setValue('ChangeMe_Emp12!')
  }

  it('renders the valid invite form', async () => {
    const { wrapper } = await mountView(ActivateAccountView, '/activate-account')

    expect(wrapper.get('h1').text()).toMatch(/Activate account/i)
    expect(inputByLabel(wrapper, 'Employee ID').element).toBeTruthy()
    expect(inputByLabel(wrapper, 'Work email').attributes('type')).toBe('email')
    expect(inputByLabel(wrapper, 'Invite token').element).toBeTruthy()
    expect(inputByLabel(wrapper, 'New password').attributes('type')).toBe('password')
    expect(namedButton(wrapper, 'Activate').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('a[href="/sign-in"]').text()).toMatch(/Sign in/i)
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
  })

  it('shows expired copy when activate-account reports an expired invite', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toContain('/api/auth/activate-account')
      expect(init?.method).toBe('POST')
      expect(JSON.parse(String(init?.body))).toEqual({
        employee_code: 'EMP-1001',
        email: 'new.hire@dayflow.demo',
        token: 'invite-token-1',
        password: 'ChangeMe_Emp12!',
      })
      return jsonResponse(400, { detail: 'This invite has expired.' })
    })

    const { wrapper } = await mountView(ActivateAccountView, '/activate-account')
    await fillValidInvite(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toMatch(/expired/i)
    expect(wrapper.text()).toMatch(/Invite expired/i)
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('shows already-used copy when activate-account reports a used invite', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(400, { detail: 'This invite has already been used.' }),
    )

    const { wrapper } = await mountView(ActivateAccountView, '/activate-account')
    await fillValidInvite(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toMatch(/already been used|already used/i)
    expect(wrapper.text()).toMatch(/Already used/i)
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('still treats 410 expired and 409 used as dedicated screens', async () => {
    fetchMock.mockImplementation(() => jsonResponse(410, { detail: 'Gone.' }))
    const expired = await mountView(ActivateAccountView, '/activate-account')
    await fillValidInvite(expired.wrapper)
    await expired.wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(expired.wrapper.text()).toMatch(/Invite expired/i)
    expired.wrapper.unmount()

    fetchMock.mockImplementation(() => jsonResponse(409, { detail: 'Conflict.' }))
    const used = await mountView(ActivateAccountView, '/activate-account')
    await fillValidInvite(used.wrapper)
    await used.wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(used.wrapper.text()).toMatch(/Already used/i)
    used.wrapper.unmount()
  })

  it('keeps the form for other 400 activation errors', async () => {
    fetchMock.mockImplementation(() => jsonResponse(400, { detail: 'Invite is invalid.' }))

    const { wrapper } = await mountView(ActivateAccountView, '/activate-account')
    await fillValidInvite(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('form').exists()).toBe(true)
    expect(wrapper.get('[role="alert"]').text()).toMatch(/Invite is invalid/i)
    expect(wrapper.text()).not.toMatch(/Invite expired/i)
    expect(wrapper.text()).not.toMatch(/Already used/i)
  })

  it('shows verification-sent copy after a successful activate-account response', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(200, {
        status: 'verification_sent',
        detail: 'Check your work email to verify this account.',
      }),
    )

    const { wrapper } = await mountView(ActivateAccountView, '/activate-account')
    await fillValidInvite(wrapper)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalled()
    const [url, init] = fetchMock.mock.calls[0] as [RequestInfo, RequestInit]
    expect(String(url)).toContain('/api/auth/activate-account')
    expect(init.method).toBe('POST')
    expect(wrapper.get('[role="status"]').text()).toMatch(/Verification sent/i)
    expect(wrapper.text()).toMatch(/work email/i)
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('shows the verified frame from the email-verification landing query', async () => {
    const { wrapper } = await mountView(ActivateAccountView, '/activate-account', { verified: '1' })

    expect(wrapper.get('[role="status"]').text()).toMatch(/verified/i)
    expect(wrapper.text()).toMatch(/Email verified|verified/i)
    expect(wrapper.get('a[href="/sign-in"]').element).toBeTruthy()
    expect(wrapper.find('form').exists()).toBe(false)
  })
})
