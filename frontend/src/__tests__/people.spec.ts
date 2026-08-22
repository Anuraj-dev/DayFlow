import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import { useSessionStore } from '@/stores/session'
import type { EmployeeSummary, Role, SessionUser } from '@/types/domain'
import EmployeeProfileView from '@/views/EmployeeProfileView.vue'
import EmployeesView from '@/views/EmployeesView.vue'

type FetchMock = ReturnType<typeof vi.fn>

const SELF_ID = '33333333-3333-3333-3333-333333333333'
const OTHER_ID = '44444444-4444-4444-4444-444444444444'

function jsonResponse(status: number, body: unknown): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

function sessionUser(role: Role, employeeId = SELF_ID): SessionUser {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    email: role === 'HR' ? 'hr@dayflow.demo' : 'employee@dayflow.demo',
    role,
    organization_id: '22222222-2222-2222-2222-222222222222',
    employee_id: employeeId,
    first_name: role === 'HR' ? 'Hari' : 'Rohan',
    last_name: role === 'HR' ? 'Rao' : 'Iyer',
    employee_code: role === 'HR' ? 'HR-001' : 'EMP-014',
  }
}

function person(overrides: Partial<EmployeeSummary> = {}): EmployeeSummary {
  return {
    id: SELF_ID,
    employee_code: 'EMP-014',
    first_name: 'Rohan',
    last_name: 'Iyer',
    status: 'ACTIVE',
    email: 'employee@dayflow.demo',
    role: 'EMPLOYEE',
    phone: '+91-90000-11114',
    address: 'Bengaluru',
    department: 'Operations',
    title: 'Associate',
    employment_type: 'FULL_TIME',
    location: 'Bengaluru',
    joined_on: '2024-01-08',
    ...overrides,
  }
}

function inputByLabel(wrapper: VueWrapper, labelText: string) {
  const label = wrapper.findAll('label').find((node) => node.text().includes(labelText))
  expect(label, `missing label "${labelText}"`).toBeTruthy()
  const control = label!.find('input, textarea, select')
  expect(control.exists(), `missing field for "${labelText}"`).toBe(true)
  return control
}

function namedButton(wrapper: VueWrapper, text: string) {
  const button = wrapper.findAll('button').find((node) => node.text().includes(text))
  expect(button, `missing button "${text}"`).toBeTruthy()
  return button!
}

function tabTrigger(wrapper: VueWrapper, text: string) {
  const trigger = wrapper
    .findAll('button, [role="tab"]')
    .find((node) => node.text().trim() === text)
  expect(trigger, `missing tab "${text}"`).toBeTruthy()
  return trigger!
}

async function mountDirectory() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useSessionStore().user = sessionUser('HR')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/employees', name: 'employees', component: EmployeesView },
      {
        path: '/employees/:employeeId',
        name: 'employee-profile',
        component: EmployeeProfileView,
      },
    ],
  })
  await router.push('/employees')
  await router.isReady()
  const wrapper = mount(EmployeesView, { global: { plugins: [pinia, router] } })
  return { wrapper, router }
}

async function mountProfile(path: string, role: Role, employeeId = SELF_ID): Promise<{
  wrapper: VueWrapper
  router: Router
}> {
  const pinia = createPinia()
  setActivePinia(pinia)
  useSessionStore().user = sessionUser(role, employeeId)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/employees/:employeeId', name: 'employee-profile', component: EmployeeProfileView },
      { path: '/dashboard', name: 'dashboard', component: EmployeesView },
    ],
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(EmployeeProfileView, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('HR people directory', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn(() => Promise.reject(new Error('Unexpected fetch')))
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.setItem('dayflow.token', 'test-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
  })

  it('shows a loading state while /api/employees is in flight', async () => {
    let resolveList: ((value: Response) => void) | undefined
    fetchMock.mockImplementation(
      () =>
        new Promise<Response>((resolve) => {
          resolveList = resolve
        }),
    )

    const { wrapper } = await mountDirectory()
    await nextTick()

    expect(wrapper.text()).toMatch(/Loading people/i)
    expect(wrapper.find('table').exists()).toBe(false)

    resolveList!(
      await jsonResponse(200, [
        person({ id: OTHER_ID, employee_code: 'EMP-020', first_name: 'Nia', last_name: 'Shah' }),
      ]),
    )
    await flushPromises()
    expect(wrapper.get('table').text()).toMatch(/EMP-020/)
  })

  it('shows an empty directory when /api/employees returns no people', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      expect(String(input)).toContain('/api/employees')
      return jsonResponse(200, [])
    })

    const { wrapper } = await mountDirectory()
    await flushPromises()

    expect(wrapper.text()).toMatch(/No employees/i)
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('shows no results when the filter matches nobody', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(200, [person(), person({ id: OTHER_ID, employee_code: 'HR-001', first_name: 'Hari', last_name: 'Rao', role: 'HR' })]),
    )

    const { wrapper } = await mountDirectory()
    await flushPromises()

    await inputByLabel(wrapper, 'Filter people').setValue('zzz-no-match')
    await nextTick()

    expect(wrapper.text()).toMatch(/No results/i)
    expect(wrapper.text()).toMatch(/No people match this filter/i)
    expect(wrapper.find('tbody').exists()).toBe(false)
  })

  it('renders inactive employees with Inactive status text in the directory table', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(200, [
        person(),
        person({
          id: OTHER_ID,
          employee_code: 'EMP-009',
          first_name: 'Leela',
          last_name: 'Nair',
          status: 'INACTIVE',
          title: 'Analyst',
          department: 'Finance',
        }),
      ]),
    )

    const { wrapper } = await mountDirectory()
    await flushPromises()

    const table = wrapper.get('table')
    expect(table.text()).toMatch(/EMP-009/)
    expect(table.text()).toMatch(/Leela Nair/)
    expect(table.text()).toMatch(/Finance/)
    const statuses = wrapper.findAll('[data-tone]').map((node) => node.text().trim())
    expect(statuses).toContain('Active')
    expect(statuses).toContain('Inactive')

    await inputByLabel(wrapper, 'Status').setValue('INACTIVE')
    await nextTick()

    expect(wrapper.get('table').text()).toMatch(/Leela Nair/)
    expect(wrapper.get('table').text()).not.toMatch(/Rohan Iyer/)
  })
})

describe('Employee profile form sheet', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn(() => Promise.reject(new Error('Unexpected fetch')))
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.setItem('dayflow.token', 'test-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
  })

  it('shows access denied when an employee opens another id and /api/employees/:id returns 403', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      expect(String(input)).toContain(`/api/employees/${OTHER_ID}`)
      return jsonResponse(403, { detail: 'Employees can read only their own record.' })
    })

    const { wrapper } = await mountProfile(`/employees/${OTHER_ID}`, 'EMPLOYEE')

    const alert = wrapper.get('[role="alert"]')
    expect(alert.text()).toMatch(/Access denied/i)
    expect(alert.text()).toMatch(/Employees can read only their own record/i)
    expect(wrapper.text()).not.toMatch(/Personal/)
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('loads a view-mode form sheet with Personal, Job, Salary, and Documents tabs', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/payroll')) {
        return jsonResponse(200, {
          role: 'EMPLOYEE',
          periods: [],
          records: [{ id: 'r1', net_amount: '42000.00', currency: 'INR', published_at: '2026-08-01T00:00:00Z' }],
        })
      }
      expect(url).toContain(`/api/employees/${SELF_ID}`)
      return jsonResponse(200, person())
    })

    const { wrapper } = await mountProfile(`/employees/${SELF_ID}`, 'EMPLOYEE')

    expect(wrapper.get('h1').text()).toMatch(/Rohan Iyer/)
    expect(wrapper.text()).toMatch(/Personal/)
    expect(wrapper.text()).toMatch(/Job/)
    expect(wrapper.text()).toMatch(/Salary/)
    expect(wrapper.text()).toMatch(/Documents/)

    expect(inputByLabel(wrapper, 'Phone').element).toHaveProperty('disabled', true)
    expect(inputByLabel(wrapper, 'Address').element).toHaveProperty('disabled', true)
    expect(namedButton(wrapper, 'Edit').attributes('disabled')).toBeUndefined()
    expect(wrapper.findAll('button').some((node) => node.text().includes('Save'))).toBe(false)
  })

  it('enters edit mode, flags unsaved changes, and PATCHes permitted personal fields', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/payroll')) {
        return jsonResponse(200, { role: 'EMPLOYEE', periods: [], records: [] })
      }
      if (init?.method === 'PATCH') {
        expect(url).toContain(`/api/employees/${SELF_ID}`)
        expect(JSON.parse(String(init.body))).toEqual({
          phone: '+91-90000-22222',
          address: 'Mysuru',
        })
        return jsonResponse(200, person({ phone: '+91-90000-22222', address: 'Mysuru' }))
      }
      return jsonResponse(200, person())
    })

    const { wrapper } = await mountProfile(`/employees/${SELF_ID}`, 'EMPLOYEE')
    await namedButton(wrapper, 'Edit').trigger('click')
    await nextTick()

    const phone = inputByLabel(wrapper, 'Phone')
    const address = inputByLabel(wrapper, 'Address')
    expect(phone.attributes('disabled')).toBeUndefined()
    expect(address.attributes('disabled')).toBeUndefined()
    expect(inputByLabel(wrapper, 'First name').attributes('disabled')).toBeDefined()

    await phone.setValue('+91-90000-22222')
    await address.setValue('Mysuru')
    await nextTick()

    expect(wrapper.text()).toMatch(/Unsaved changes/i)
    expect(namedButton(wrapper, 'Save').attributes('disabled')).toBeUndefined()

    await namedButton(wrapper, 'Save').trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toMatch(/Unsaved changes/i)
    expect((inputByLabel(wrapper, 'Phone').element as HTMLInputElement).value).toBe('+91-90000-22222')
    expect(wrapper.text()).toMatch(/Profile saved/i)
    expect(wrapper.findAll('button').some((node) => node.text().includes('Save'))).toBe(false)
  })

  it('lets HR edit job fields and keeps salary on the Salary tab', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/payroll')) {
        return jsonResponse(200, {
          role: 'HR',
          periods: [],
          records: [{ id: 'r1', employee_id: SELF_ID, net_amount: '42000.00', currency: 'INR', published_at: null }],
        })
      }
      if (init?.method === 'PATCH') {
        expect(JSON.parse(String(init.body))).toEqual({
          title: 'Senior Associate',
        })
        return jsonResponse(200, person({ title: 'Senior Associate' }))
      }
      return jsonResponse(200, person())
    })

    const { wrapper } = await mountProfile(`/employees/${SELF_ID}`, 'HR')
    await namedButton(wrapper, 'Edit').trigger('click')
    await tabTrigger(wrapper, 'Job').trigger('click')
    await nextTick()

    await inputByLabel(wrapper, 'Title').setValue('Senior Associate')
    await nextTick()
    expect(wrapper.text()).toMatch(/Unsaved changes/i)

    await namedButton(wrapper, 'Save').trigger('click')
    await flushPromises()

    await tabTrigger(wrapper, 'Salary').trigger('click')
    await nextTick()
    expect(wrapper.text()).toMatch(/₹42,000\.00/)
    expect(wrapper.text()).toMatch(/read-only|Payroll/i)
  })

  it('shows a deferred Documents tab with a missing-document status', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/api/payroll')) {
        return jsonResponse(200, { role: 'EMPLOYEE', periods: [], records: [] })
      }
      return jsonResponse(200, person())
    })

    const { wrapper } = await mountProfile(`/employees/${SELF_ID}`, 'EMPLOYEE')
    await tabTrigger(wrapper, 'Documents').trigger('click')
    await nextTick()

    expect(wrapper.text()).toMatch(/not available yet/i)
    expect(wrapper.text()).toMatch(/Missing document/i)
    expect(wrapper.text()).not.toMatch(/upload is ready/i)
  })
})
