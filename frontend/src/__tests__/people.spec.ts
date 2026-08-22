import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import { useSessionStore } from '@/stores/session'
import type { EmployeeSalary, EmployeeSummary, Role, SessionUser } from '@/types/domain'
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

function salaryBreakdown(overrides: Partial<EmployeeSalary> = {}): EmployeeSalary {
  return {
    employee_id: SELF_ID,
    monthly_wage: '50000.00',
    currency: 'INR',
    effective_from: '2025-03-03',
    gross_amount: '50000.00',
    deduction_amount: '3200.00',
    net_amount: '46800.00',
    employer_amount: '3000.00',
    lines: [
      {
        code: 'BASIC',
        name: 'Basic',
        kind: 'EARNING',
        calculation_type: 'PERCENT_OF_WAGE',
        rate: '50.00',
        amount: '25000.00',
        editable: true,
      },
      {
        code: 'HRA',
        name: 'House rent allowance',
        kind: 'EARNING',
        calculation_type: 'PERCENT_OF_BASIC',
        rate: '50.00',
        amount: '12500.00',
        editable: true,
      },
      {
        code: 'STD_ALLOW',
        name: 'Standard Allowance',
        kind: 'EARNING',
        calculation_type: 'FIXED',
        rate: null,
        amount: '4167.00',
        editable: true,
      },
      {
        code: 'FIXED_ALLOW',
        name: 'Fixed Allowance',
        kind: 'EARNING',
        calculation_type: 'REMAINDER',
        rate: null,
        amount: '3.00',
        editable: false,
      },
      {
        code: 'PF',
        name: 'Employee provident fund',
        kind: 'DEDUCTION',
        calculation_type: 'PERCENT_OF_BASIC',
        rate: '12.00',
        amount: '3000.00',
        editable: false,
      },
      {
        code: 'PF_EMPLOYER',
        name: 'Employer provident fund',
        kind: 'EMPLOYER',
        calculation_type: 'PERCENT_OF_BASIC',
        rate: '12.00',
        amount: '3000.00',
        editable: false,
      },
      {
        code: 'PT',
        name: 'Professional tax',
        kind: 'DEDUCTION',
        calculation_type: 'FIXED',
        rate: null,
        amount: '200.00',
        editable: false,
      },
    ],
    ...overrides,
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
    expect(namedButton(wrapper, 'New').exists()).toBe(true)
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
      if (url.includes('/salary')) {
        return jsonResponse(200, salaryBreakdown())
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
      if (url.includes('/salary')) {
        return jsonResponse(200, salaryBreakdown())
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
      if (url.includes('/salary') && init?.method === 'PATCH') {
        const body = JSON.parse(String(init.body)) as { monthly_wage: string }
        return jsonResponse(200, salaryBreakdown({ monthly_wage: body.monthly_wage, net_amount: '56200.00' }))
      }
      if (url.includes('/salary')) {
        return jsonResponse(200, salaryBreakdown())
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
    expect((inputByLabel(wrapper, 'Monthly wage').element as HTMLInputElement).value).toBe('50000.00')
    expect(wrapper.text()).toMatch(/₹25,000\.00/)
    expect(wrapper.text()).toMatch(/₹46,800\.00/)
    expect(wrapper.text()).toMatch(/Computed/)
    expect(inputByLabel(wrapper, 'Monthly wage').attributes('disabled')).toBeUndefined()
    expect(inputByLabel(wrapper, 'BASIC rate').attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).toMatch(/Fixed Allowance/)
    expect(wrapper.findAll('label').some((node) => node.text().includes('FIXED_ALLOW'))).toBe(false)
    await inputByLabel(wrapper, 'Monthly wage').setValue('60000.00')
    await namedButton(wrapper, 'Save salary').trigger('click')
    await flushPromises()
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url) === `/api/payroll/employees/${SELF_ID}/salary` &&
          (init as RequestInit | undefined)?.method === 'PATCH',
      ),
    ).toBe(true)
    expect(wrapper.text()).toMatch(/Salary saved/)
  })

  it('shows Private and Bank tabs for self, with private fields disabled for employees', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/salary')) {
        return jsonResponse(200, salaryBreakdown())
      }
      return jsonResponse(
        200,
        person({
          date_of_birth: '1994-04-12',
          nationality: 'Indian',
          gender: 'MALE',
          marital_status: 'SINGLE',
          personal_email: 'rohan.personal@example.com',
          bank_account_number: '123456789012',
          bank_name: 'HDFC Bank',
          ifsc: 'HDFC0001234',
          pan: 'ABCDE1234F',
          uan: '100123456789',
        }),
      )
    })

    const { wrapper } = await mountProfile(`/employees/${SELF_ID}`, 'EMPLOYEE')
    expect(wrapper.text()).toMatch(/Private/)
    expect(wrapper.text()).toMatch(/Bank/)
    expect(wrapper.text()).toMatch(/Security/)

    await namedButton(wrapper, 'Edit').trigger('click')
    await tabTrigger(wrapper, 'Private').trigger('click')
    await nextTick()
    expect(inputByLabel(wrapper, 'Date of birth').attributes('disabled')).toBeDefined()
    expect(inputByLabel(wrapper, 'Personal email').attributes('disabled')).toBeDefined()
    expect((inputByLabel(wrapper, 'Personal email').element as HTMLInputElement).value).toBe(
      'rohan.personal@example.com',
    )

    await tabTrigger(wrapper, 'Bank').trigger('click')
    await nextTick()
    expect(inputByLabel(wrapper, 'PAN').attributes('disabled')).toBeDefined()
    expect((inputByLabel(wrapper, 'PAN').element as HTMLInputElement).value).toBe('ABCDE1234F')
  })

  it('lets HR edit bank fields from the Bank tab', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/salary')) {
        return jsonResponse(200, salaryBreakdown())
      }
      if (init?.method === 'PATCH') {
        expect(JSON.parse(String(init.body))).toEqual({ pan: 'XYZAB9876C' })
        return jsonResponse(200, person({ pan: 'XYZAB9876C' }))
      }
      return jsonResponse(200, person({ pan: 'ABCDE1234F' }))
    })

    const { wrapper } = await mountProfile(`/employees/${SELF_ID}`, 'HR')
    await namedButton(wrapper, 'Edit').trigger('click')
    await tabTrigger(wrapper, 'Bank').trigger('click')
    await nextTick()
    expect(inputByLabel(wrapper, 'PAN').attributes('disabled')).toBeUndefined()
    await inputByLabel(wrapper, 'PAN').setValue('XYZAB9876C')
    await nextTick()
    await namedButton(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect((inputByLabel(wrapper, 'PAN').element as HTMLInputElement).value).toBe('XYZAB9876C')
  })

  it('hides Private, Bank, and Security tabs on a coworker profile', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/salary')) {
        return jsonResponse(403, { detail: 'Salary is visible only to HR or the employee.' })
      }
      return jsonResponse(200, person({ id: OTHER_ID, first_name: 'Hari', last_name: 'Rao' }))
    })

    const { wrapper } = await mountProfile(`/employees/${OTHER_ID}`, 'EMPLOYEE', SELF_ID)
    expect(wrapper.text()).toMatch(/Personal/)
    expect(wrapper.text()).not.toMatch(/\bPrivate\b/)
    expect(wrapper.text()).not.toMatch(/\bBank\b/)
    expect(wrapper.text()).not.toMatch(/Security/)
    expect(wrapper.text()).not.toMatch(/ABCDE1234F/)
  })

  it('submits change-password from the Security tab and shows wrong-current-password errors', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/salary')) {
        return jsonResponse(200, salaryBreakdown())
      }
      if (url.includes('/api/auth/change-password')) {
        expect(init?.method).toBe('POST')
        const body = JSON.parse(String(init?.body)) as {
          current_password: string
          new_password: string
        }
        if (body.current_password !== 'ChangeMe_Emp12!') {
          return jsonResponse(400, { detail: 'Current password is incorrect.' })
        }
        expect(body).toEqual({
          current_password: 'ChangeMe_Emp12!',
          new_password: 'ChangeMe_New12!',
        })
        return jsonResponse(200, { detail: 'Password changed.' })
      }
      return jsonResponse(200, person())
    })

    const { wrapper } = await mountProfile(`/employees/${SELF_ID}`, 'EMPLOYEE')
    await tabTrigger(wrapper, 'Security').trigger('click')
    await nextTick()

    await inputByLabel(wrapper, 'Current password').setValue('WrongPassword1!')
    await inputByLabel(wrapper, 'New password').setValue('ChangeMe_New12!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toMatch(/Current password is incorrect/i)

    await inputByLabel(wrapper, 'Current password').setValue('ChangeMe_Emp12!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toMatch(/Password changed/i)
  })

  it('shows a deferred Documents tab with a missing-document status', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/salary')) {
        return jsonResponse(200, salaryBreakdown())
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

  it('shows a read-only computed salary breakdown for the employee', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/salary')) return jsonResponse(200, salaryBreakdown())
      return jsonResponse(200, person())
    })

    const { wrapper } = await mountProfile(`/employees/${SELF_ID}`, 'EMPLOYEE')
    await tabTrigger(wrapper, 'Salary').trigger('click')
    await nextTick()

    expect(wrapper.text()).toMatch(/₹25,000\.00/)
    expect(wrapper.text()).toMatch(/₹12,500\.00/)
    expect(wrapper.text()).toMatch(/Employee provident fund/)
    expect(wrapper.text()).toMatch(/Employer contribution/)
    expect(inputByLabel(wrapper, 'Monthly wage').attributes('disabled')).toBeDefined()
    expect(wrapper.findAll('button').some((node) => node.text().includes('Save salary'))).toBe(false)
  })

  it('hides coworker salary when the salary endpoint returns 403', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/salary')) {
        return jsonResponse(403, { detail: 'Salary is visible only to HR or the employee.' })
      }
      return jsonResponse(200, person({ id: OTHER_ID, first_name: 'Hari', last_name: 'Rao' }))
    })

    const { wrapper } = await mountProfile(`/employees/${OTHER_ID}`, 'EMPLOYEE', SELF_ID)
    await tabTrigger(wrapper, 'Salary').trigger('click')
    await nextTick()

    expect(wrapper.text()).toMatch(/Salary is hidden/)
    expect(wrapper.text()).not.toMatch(/₹25,000\.00/)
    expect(wrapper.text()).not.toMatch(/50000/)
  })
})
