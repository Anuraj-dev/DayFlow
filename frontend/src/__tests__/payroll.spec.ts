import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'

import AppShell from '@/layouts/AppShell.vue'
import { useSessionStore } from '@/stores/session'
import type {
  EmployeeSalaryInputs,
  EmployeeSummary,
  PayrollHome,
  PayrollPeriod,
  PayrollRecord,
  Role,
  SessionUser,
} from '@/types/domain'
import PayrollView from '@/views/PayrollView.vue'
import SettingsView from '@/views/SettingsView.vue'

type FetchMock = ReturnType<typeof vi.fn>

const SELF_ID = '33333333-3333-3333-3333-333333333333'
const OTHER_ID = '44444444-4444-4444-4444-444444444444'
const CURRENT_PERIOD = 'period-current'
const PRIOR_PERIOD = 'period-prior'
const DRAFT_PERIOD = 'period-draft'

function jsonResponse(status: number, body: unknown): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

function sessionUser(role: Role): SessionUser {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    email: role === 'HR' ? 'hr@dayflow.demo' : 'employee@dayflow.demo',
    role,
    organization_id: '22222222-2222-2222-2222-222222222222',
    employee_id: SELF_ID,
    first_name: role === 'HR' ? 'Hari' : 'Rohan',
    last_name: role === 'HR' ? 'Rao' : 'Iyer',
    employee_code: role === 'HR' ? 'HR-001' : 'EMP-014',
  }
}

function period(overrides: Partial<PayrollPeriod> = {}): PayrollPeriod {
  return {
    id: CURRENT_PERIOD,
    starts_on: '2026-08-01',
    ends_on: '2026-08-31',
    pay_date: '2026-09-05',
    status: 'PUBLISHED',
    ...overrides,
  }
}

function record(overrides: Partial<PayrollRecord> = {}): PayrollRecord {
  return {
    id: 'rec-current',
    employee_id: SELF_ID,
    employee_name: 'Rohan Iyer',
    payroll_period_id: CURRENT_PERIOD,
    gross_amount: '56000.00',
    deduction_amount: '4800.00',
    net_amount: '51200.00',
    currency: 'INR',
    published_at: '2026-09-02T00:00:00Z',
    lines: [
      { code: 'BASIC', label: 'Basic', amount: '40000.00' },
      { code: 'HRA', label: 'House rent allowance', amount: '16000.00' },
      { code: 'PF', label: 'Provident fund', amount: '-4800.00' },
    ],
    ...overrides,
  }
}

function salaryInputs(overrides: Partial<EmployeeSalaryInputs> = {}): EmployeeSalaryInputs {
  return {
    employee_id: SELF_ID,
    employee_name: 'Rohan Iyer',
    components: [
      { code: 'BASIC', name: 'Basic', kind: 'EARNING', amount: '40000.00' },
      { code: 'HRA', name: 'House rent allowance', kind: 'EARNING', amount: '16000.00' },
      { code: 'PF', name: 'Provident fund', kind: 'DEDUCTION', amount: '4800.00' },
    ],
    ...overrides,
  }
}

function home(overrides: Partial<PayrollHome> = {}): PayrollHome {
  return {
    role: 'EMPLOYEE',
    periods: [period()],
    records: [record()],
    ...overrides,
  }
}

function people(): EmployeeSummary[] {
  return [
    {
      id: SELF_ID,
      employee_code: 'EMP-014',
      first_name: 'Rohan',
      last_name: 'Iyer',
      status: 'ACTIVE',
    },
    {
      id: OTHER_ID,
      employee_code: 'HR-001',
      first_name: 'Hari',
      last_name: 'Rao',
      status: 'ACTIVE',
      role: 'HR',
    },
  ]
}

function namedButton(wrapper: VueWrapper, text: string) {
  const button = wrapper.findAll('button').find((node) => node.text().includes(text))
  expect(button, `missing button "${text}"`).toBeTruthy()
  return button!
}

function inputByLabel(wrapper: VueWrapper, labelText: string) {
  const label = wrapper.findAll('label').find((node) => node.text().includes(labelText))
  expect(label, `missing label "${labelText}"`).toBeTruthy()
  const control = label!.find('input, textarea, select')
  expect(control.exists(), `missing field for "${labelText}"`).toBe(true)
  return control
}

async function mountPayroll(role: Role, path = '/payroll') {
  const pinia = createPinia()
  setActivePinia(pinia)
  useSessionStore().user = sessionUser(role)
  const stub = defineComponent({ setup: () => () => h('p', 'Overview') })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        component: AppShell,
        children: [
          { path: 'dashboard', name: 'dashboard', component: stub, meta: { title: 'Overview' } },
          { path: 'employees', name: 'employees', component: stub, meta: { title: 'People', hrOnly: true } },
          { path: 'attendance', name: 'attendance', component: stub, meta: { title: 'Attendance' } },
          { path: 'time-off', name: 'time-off', component: stub, meta: { title: 'Time off' } },
          { path: 'payroll', name: 'payroll', component: PayrollView, meta: { title: 'Payroll' } },
          {
            path: 'settings',
            name: 'settings',
            component: SettingsView,
            meta: { title: 'Settings', hrOnly: true },
          },
        ],
      },
    ],
  })
  router.beforeEach((to) => {
    const session = useSessionStore()
    if (to.meta.hrOnly && !session.isHr) return { name: 'dashboard' }
    return true
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(
    defineComponent({
      setup: () => () => h(RouterView),
    }),
    {
      attachTo: document.body,
      global: { plugins: [pinia, router] },
    },
  )
  await flushPromises()
  return { wrapper, router }
}

describe('Employee payroll', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn(() => jsonResponse(200, home()))
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.setItem('dayflow.token', 'test-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
    document.body.innerHTML = ''
  })

  it('shows the current published payslip with period summary and download', async () => {
    const { wrapper } = await mountPayroll('EMPLOYEE')
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/payroll')).toBe(true)
    expect(wrapper.text()).toMatch(/Current period/)
    expect(wrapper.text()).toMatch(/Aug 1, 2026/)
    expect(wrapper.text()).toMatch(/Aug 31, 2026/)
    expect(wrapper.text()).toMatch(/Sep 5, 2026/)
    expect(wrapper.text()).toMatch(/Published/)
    expect(wrapper.text()).toMatch(/₹51,200\.00/)
    expect(wrapper.text()).toMatch(/Basic/)
    expect(namedButton(wrapper, 'Download payslip').exists()).toBe(true)
    expect(wrapper.text()).not.toMatch(/\bFinalize\b/)
    expect(wrapper.text()).not.toMatch(/\bPublish\b/)
    expect(wrapper.text()).not.toMatch(/Save salary/)
  })

  it('lists a prior published period separately from the current payslip', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(
        200,
        home({
          periods: [
            period(),
            period({
              id: PRIOR_PERIOD,
              starts_on: '2026-07-01',
              ends_on: '2026-07-31',
              pay_date: '2026-08-05',
            }),
          ],
          records: [
            record(),
            record({
              id: 'rec-prior',
              payroll_period_id: PRIOR_PERIOD,
              net_amount: '49800.00',
              published_at: '2026-08-02T00:00:00Z',
            }),
          ],
        }),
      ),
    )

    const { wrapper } = await mountPayroll('EMPLOYEE')
    expect(wrapper.text()).toMatch(/Current period/)
    expect(wrapper.text()).toMatch(/Prior period/)
    expect(wrapper.text()).toMatch(/Jul 1, 2026/)
    expect(wrapper.text()).toMatch(/₹49,800\.00/)
  })

  it('shows no published payslip when the employee has none', async () => {
    fetchMock.mockImplementation(() => jsonResponse(200, home({ periods: [], records: [] })))
    const { wrapper } = await mountPayroll('EMPLOYEE')
    expect(wrapper.text()).toMatch(/No published payslip/)
    expect(wrapper.text()).not.toMatch(/Download payslip/)
  })

  it('hides draft periods and unpublished records from the employee view', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(
        200,
        home({
          role: 'EMPLOYEE',
          periods: [
            period(),
            period({
              id: DRAFT_PERIOD,
              starts_on: '2026-09-01',
              ends_on: '2026-09-30',
              pay_date: '2026-10-05',
              status: 'DRAFT',
            }),
          ],
          records: [
            record(),
            record({
              id: 'rec-draft',
              payroll_period_id: DRAFT_PERIOD,
              net_amount: '99999.00',
              published_at: null,
            }),
          ],
        }),
      ),
    )

    const { wrapper } = await mountPayroll('EMPLOYEE')
    expect(wrapper.text()).toMatch(/Published/)
    expect(wrapper.text()).toMatch(/₹51,200\.00/)
    expect(wrapper.text()).not.toMatch(/₹99,999\.00/)
    expect(wrapper.text()).not.toMatch(/Sep 1, 2026/)
    expect(wrapper.text()).not.toMatch(/\bDraft\b/)
    expect(wrapper.text()).not.toMatch(/\bFinalize\b/)
  })

  it('keeps download wired when GET payslip returns 501', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/payslip')) {
        return jsonResponse(501, { detail: 'Payslip download is not implemented.' })
      }
      return jsonResponse(200, home())
    })

    const { wrapper } = await mountPayroll('EMPLOYEE')
    await namedButton(wrapper, 'Download payslip').trigger('click')
    await flushPromises()
    expect(
      fetchMock.mock.calls.some(([url]) => String(url) === `/api/payroll/records/rec-current/payslip`),
    ).toBe(true)
    expect(wrapper.get('[role="alert"]').text()).toMatch(/not implemented|Payslip/i)
  })
})

describe('HR payroll control', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/api/employees')) return jsonResponse(200, people())
      return jsonResponse(
        200,
        home({
          role: 'HR',
          periods: [
            period({
              id: DRAFT_PERIOD,
              starts_on: '2026-09-01',
              ends_on: '2026-09-30',
              pay_date: '2026-10-05',
              status: 'DRAFT',
            }),
          ],
          records: [],
          salary_inputs: [salaryInputs()],
        }),
      )
    })
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.setItem('dayflow.token', 'test-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
    document.body.innerHTML = ''
  })

  it('lets HR edit salary only while the period is draft', async () => {
    const { wrapper } = await mountPayroll('HR')
    expect(wrapper.text()).toMatch(/Payroll control/)
    expect(wrapper.text()).toMatch(/Draft/)
    expect(wrapper.text()).toMatch(/Rohan Iyer/)
    expect(inputByLabel(wrapper, 'BASIC').attributes('disabled')).toBeUndefined()
    expect(namedButton(wrapper, 'Finalize').attributes('disabled')).toBeUndefined()
    expect(wrapper.text()).not.toMatch(/Publish payslips/)
    expect(namedButton(wrapper, 'Save salary').attributes('disabled')).toBeUndefined()
  })

  it('PATCHes /api/payroll/salary-components from the draft salary sheet', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === '/api/payroll/salary-components' && init?.method === 'PATCH') {
        const body = JSON.parse(String(init.body)) as {
          employee_id: string
          period_id: string
          components: { code: string; amount: string }[]
        }
        expect(body.employee_id).toBe(SELF_ID)
        expect(body.period_id).toBe(DRAFT_PERIOD)
        expect(body.components).toEqual(
          expect.arrayContaining([{ code: 'BASIC', amount: '42000.00' }]),
        )
        return jsonResponse(200, {
          employee_id: SELF_ID,
          components: [
            { code: 'BASIC', name: 'Basic', kind: 'EARNING', amount: '42000.00' },
            { code: 'HRA', name: 'House rent allowance', kind: 'EARNING', amount: '16000.00' },
            { code: 'PF', name: 'Provident fund', kind: 'DEDUCTION', amount: '4800.00' },
          ],
        })
      }
      if (url.includes('/api/employees')) return jsonResponse(200, people())
      return jsonResponse(
        200,
        home({
          role: 'HR',
          periods: [
            period({
              id: DRAFT_PERIOD,
              starts_on: '2026-09-01',
              ends_on: '2026-09-30',
              pay_date: '2026-10-05',
              status: 'DRAFT',
            }),
          ],
          records: [],
          salary_inputs: [salaryInputs()],
        }),
      )
    })

    const { wrapper } = await mountPayroll('HR')
    await inputByLabel(wrapper, 'BASIC').setValue('42000.00')
    await namedButton(wrapper, 'Save salary').trigger('click')
    await flushPromises()
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url) === '/api/payroll/salary-components' &&
          (init as RequestInit | undefined)?.method === 'PATCH',
      ),
    ).toBe(true)
  })

  it('shows validation errors and keeps finalize wired after a 409', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/finalize') && init?.method === 'POST') {
        return jsonResponse(409, { detail: 'Net pay cannot be negative.' })
      }
      if (url.includes('/api/employees')) return jsonResponse(200, people())
      return jsonResponse(
        200,
        home({
          role: 'HR',
          periods: [
            period({
              id: DRAFT_PERIOD,
              starts_on: '2026-09-01',
              ends_on: '2026-09-30',
              pay_date: '2026-10-05',
              status: 'DRAFT',
              validation_errors: ['Missing salary data for Rohan Iyer.', 'Net pay cannot be negative.'],
            }),
          ],
          records: [],
          salary_inputs: [salaryInputs()],
        }),
      )
    })

    const { wrapper } = await mountPayroll('HR')
    expect(wrapper.text()).toMatch(/Resolve before finalizing/)
    expect(wrapper.text()).toMatch(/Missing salary data/)
    expect(wrapper.text()).toMatch(/Net pay cannot be negative/)
    expect(namedButton(wrapper, 'Finalize').attributes('disabled')).toBeDefined()
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url) === `/api/payroll/periods/${DRAFT_PERIOD}/finalize` &&
          (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(false)
    expect(wrapper.get('[role="alert"]').text()).toMatch(/negative/i)
  })

  it('locks salary after finalization and enables publish', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/api/employees')) return jsonResponse(200, people())
      return jsonResponse(
        200,
        home({
          role: 'HR',
          periods: [
            period({
              id: DRAFT_PERIOD,
              starts_on: '2026-09-01',
              ends_on: '2026-09-30',
              pay_date: '2026-10-05',
              status: 'FINALIZED',
            }),
          ],
          records: [record({ payroll_period_id: DRAFT_PERIOD, published_at: null, net_amount: '52200.00' })],
          salary_inputs: [salaryInputs()],
        }),
      )
    })

    const { wrapper } = await mountPayroll('HR')
    expect(wrapper.text()).toMatch(/Finalized/)
    expect(wrapper.text()).toMatch(/₹52,200\.00/)
    expect(inputByLabel(wrapper, 'BASIC').attributes('disabled')).toBeDefined()
    expect(namedButton(wrapper, 'Save salary').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).not.toMatch(/Finalize period/)
    expect(namedButton(wrapper, 'Publish').attributes('disabled')).toBeUndefined()
  })

  it('POSTs publish on a finalized period', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/publish') && init?.method === 'POST') {
        return jsonResponse(200, {
          id: DRAFT_PERIOD,
          starts_on: '2026-09-01',
          ends_on: '2026-09-30',
          pay_date: '2026-10-05',
          status: 'PUBLISHED',
          records: [],
        })
      }
      if (url.includes('/api/employees')) return jsonResponse(200, people())
      const published = fetchMock.mock.calls.some(
        ([called, calledInit]) =>
          String(called).includes('/publish') && (calledInit as RequestInit | undefined)?.method === 'POST',
      )
      return jsonResponse(
        200,
        home({
          role: 'HR',
          periods: [
            period({
              id: DRAFT_PERIOD,
              starts_on: '2026-09-01',
              ends_on: '2026-09-30',
              pay_date: '2026-10-05',
              status: published ? 'PUBLISHED' : 'FINALIZED',
            }),
          ],
          records: [
            record({
              payroll_period_id: DRAFT_PERIOD,
              published_at: published ? '2026-10-02T00:00:00Z' : null,
            }),
          ],
          salary_inputs: [salaryInputs()],
        }),
      )
    })

    const { wrapper } = await mountPayroll('HR')
    await namedButton(wrapper, 'Publish').trigger('click')
    await namedButton(wrapper, 'Confirm publish').trigger('click')
    await flushPromises()
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url) === `/api/payroll/periods/${DRAFT_PERIOD}/publish` &&
          (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(true)
    expect(wrapper.text()).toMatch(/Published/)
    expect(wrapper.text()).not.toMatch(/Publish payslips/)
    expect(wrapper.text()).not.toMatch(/Finalize period/)
  })

  it('shows correction needed when a published period requires an adjustment', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/api/employees')) return jsonResponse(200, people())
      return jsonResponse(
        200,
        home({
          role: 'HR',
          periods: [
            period({
              correction_needed: true,
            }),
          ],
          records: [record()],
          exceptions: [
            {
              kind: 'correction_needed',
              employee_id: SELF_ID,
              employee_name: 'Rohan Iyer',
              detail: 'Attendance exception after publish. Open an adjustment period.',
            },
          ],
          salary_inputs: [salaryInputs()],
        }),
      )
    })

    const { wrapper } = await mountPayroll('HR')
    expect(wrapper.text()).toMatch(/Correction needed/)
    expect(wrapper.text()).toMatch(/adjustment period/i)
    expect(inputByLabel(wrapper, 'BASIC').attributes('disabled')).toBeDefined()
  })
})

describe('Settings deferred policy', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn(() =>
      jsonResponse(200, {
        kind: 'EMPLOYEE',
        headline: 'Check in',
        attendance_state: 'not_checked_in',
        leave_balances: [],
        next_pay_date: null,
        incomplete_profile: false,
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.setItem('dayflow.token', 'test-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
    document.body.innerHTML = ''
  })

  it('shows the HR-only seeded policy deferred state', async () => {
    const { wrapper } = await mountPayroll('HR', '/settings')
    expect(wrapper.text()).toMatch(/Settings/)
    expect(wrapper.text()).toMatch(/Attendance source/)
    expect(wrapper.text()).toMatch(/read-only/i)
    expect(wrapper.get('nav[aria-label="Product areas"]').text()).toMatch(/Settings/)
  })

  it('redirects employees away from settings and hides the nav item', async () => {
    const { wrapper, router } = await mountPayroll('EMPLOYEE', '/settings')
    expect(router.currentRoute.value.name).toBe('dashboard')
    expect(wrapper.get('nav[aria-label="Product areas"]').text()).not.toMatch(/Settings/)
    expect(wrapper.text()).not.toMatch(/Attendance source/)
  })
})
