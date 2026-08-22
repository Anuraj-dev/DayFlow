import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'

import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { RouterView, createMemoryHistory, createRouter, type Router } from 'vue-router'

import AppShell from '@/layouts/AppShell.vue'
import { useSessionStore } from '@/stores/session'
import type { Role, SessionUser } from '@/types/domain'
import AttendanceView from '@/views/AttendanceView.vue'
import DashboardView from '@/views/DashboardView.vue'
import EmployeesView from '@/views/EmployeesView.vue'
import PayrollView from '@/views/PayrollView.vue'
import TimeOffView from '@/views/TimeOffView.vue'

const frontendRoot = resolve(process.cwd())

function readAllCss(): string {
  const stylesDir = resolve(frontendRoot, 'src/styles')
  const files = existsSync(stylesDir)
    ? readdirSync(stylesDir)
        .filter((name) => name.endsWith('.css'))
        .map((name) => readFileSync(join(stylesDir, name), 'utf8'))
    : []
  const extras = ['src/index.css', 'src/assets/index.css'].map((rel) => {
    const path = resolve(frontendRoot, rel)
    return existsSync(path) ? readFileSync(path, 'utf8') : ''
  })
  return [...files, ...extras].join('\n')
}

function jsonResponse(status: number, body: unknown): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

function employeeUser(role: Role = 'EMPLOYEE'): SessionUser {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    email: role === 'HR' ? 'hr@dayflow.demo' : 'emp@dayflow.demo',
    role,
    organization_id: '22222222-2222-2222-2222-222222222222',
    employee_id: '33333333-3333-3333-3333-333333333333',
    first_name: role === 'HR' ? 'Hari' : 'Ada',
    last_name: role === 'HR' ? 'Rao' : 'Ng',
    employee_code: role === 'HR' ? 'HR-001' : 'EMP-1001',
  }
}

async function makeAppRouter(): Promise<Router> {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        component: AppShell,
        children: [
          {
            path: 'dashboard',
            name: 'dashboard',
            component: DashboardView,
            meta: { title: 'Overview' },
          },
          {
            path: 'employees',
            name: 'employees',
            component: EmployeesView,
            meta: { title: 'People', hrOnly: true },
          },
          {
            path: 'attendance',
            name: 'attendance',
            component: AttendanceView,
            meta: { title: 'Attendance' },
          },
          {
            path: 'time-off',
            name: 'time-off',
            component: TimeOffView,
            meta: { title: 'Time off' },
          },
          {
            path: 'payroll',
            name: 'payroll',
            component: PayrollView,
            meta: { title: 'Payroll' },
          },
          {
            path: 'settings',
            name: 'settings',
            component: defineComponent({ setup: () => () => h('p', 'Settings') }),
            meta: { title: 'Settings', hrOnly: true },
          },
        ],
      },
      {
        path: '/sign-in',
        name: 'sign-in',
        component: defineComponent({ setup: () => () => h('p', 'Sign in') }),
      },
    ],
  })
}

async function mountShell(role: Role, path = '/dashboard') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const session = useSessionStore()
  session.user = employeeUser(role)
  sessionStorage.setItem('dayflow.token', 'test-token')
  const router = await makeAppRouter()
  await router.push(path)
  await router.isReady()
  const wrapper = mount(
    defineComponent({
      setup: () => () => h(RouterView),
    }),
    { global: { plugins: [pinia, router] } },
  )
  await flushPromises()
  return { wrapper, router, session }
}

describe('shadcn-vue plus Odoo 19 tokens', () => {
  it('initializes Tailwind v4 and shadcn-vue with CSS variables', () => {
    const componentsJsonPath = resolve(frontendRoot, 'components.json')
    expect(existsSync(componentsJsonPath)).toBe(true)
    const config = JSON.parse(readFileSync(componentsJsonPath, 'utf8')) as {
      tailwind?: { cssVariables?: boolean }
      aliases?: { ui?: string }
    }
    expect(config.tailwind?.cssVariables).toBe(true)
    expect(config.aliases?.ui).toMatch(/components\/ui/)
    expect(existsSync(resolve(frontendRoot, 'src/components/ui/button'))).toBe(true)
    expect(existsSync(resolve(frontendRoot, 'src/lib/utils.ts'))).toBe(true)

    const pkg = JSON.parse(readFileSync(resolve(frontendRoot, 'package.json'), 'utf8')) as {
      dependencies?: Record<string, string>
      devDependencies?: Record<string, string>
    }
    const deps = { ...pkg.dependencies, ...pkg.devDependencies }
    expect(deps.tailwindcss).toBeDefined()
    expect(deps['@tailwindcss/vite']).toBeDefined()
  })

  it('maps enterprise plum, action teal, canvas, sheet, and border tokens', () => {
    const css = readAllCss()
    expect(css).toMatch(/#714[Bb]67/)
    expect(css).toMatch(/#017[Ee]84/)
    expect(css).toMatch(/#F8F9FA/i)
    expect(css).toMatch(/#DEE2E6/i)
    expect(css).toMatch(/#212529/)
    expect(css).toMatch(/#495057/)
    expect(css).not.toMatch(/--primary:\s*#71639E/i)
    expect(css).toMatch(/46px/)
    expect(css).toMatch(/system-ui|Segoe UI|Roboto/)
  })

  it('does not ship WorkCard as page layout', () => {
    expect(existsSync(resolve(frontendRoot, 'src/components/WorkCard.vue'))).toBe(false)
  })
})

describe('AppShell chrome', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn(() => jsonResponse(200, { kind: 'EMPLOYEE', attendance_state: 'not_checked_in' }))
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
  })

  it('keeps the skip link and a 46px plum bar over a white control panel', async () => {
    const { wrapper } = await mountShell('EMPLOYEE')
    const skip = wrapper.get('a[href="#main"]')
    expect(skip.text()).toMatch(/Skip to content/i)

    const bar = wrapper.get('[data-slot="app-navbar"]')
    expect(bar.text()).toMatch(/Dayflow/)
    expect(bar.attributes('class') ?? bar.html()).toMatch(/46px|#714B67|bg-primary/)

    const panel = wrapper.get('[data-slot="control-panel"]')
    expect(panel.text()).toMatch(/Overview/)
    expect(wrapper.get('#main').element).toBeTruthy()
  })

  it('shows employee product areas and hides People and Settings', async () => {
    const { wrapper } = await mountShell('EMPLOYEE')
    const nav = wrapper.get('nav[aria-label="Product areas"]')
    expect(nav.text()).toMatch(/Overview/)
    expect(nav.text()).toMatch(/Attendance/)
    expect(nav.text()).toMatch(/Time off/)
    expect(nav.text()).toMatch(/Payroll/)
    expect(nav.text()).not.toMatch(/People/)
    expect(nav.text()).not.toMatch(/Settings/)
    expect(wrapper.get('[aria-haspopup="menu"]').text()).toMatch(/Ada Ng/)
  })

  it('adds People and Settings for HR', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(200, { kind: 'HR', headline: "Today's coverage", headcount: 2 }),
    )
    const { wrapper } = await mountShell('HR')
    const nav = wrapper.get('nav[aria-label="Product areas"]')
    expect(nav.text()).toMatch(/People/)
    expect(nav.text()).toMatch(/Settings/)
    expect(nav.text()).toMatch(/Overview/)
  })
})

describe('role-aware product views', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn(() => jsonResponse(200, {}))
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.setItem('dayflow.token', 'test-token')
    const pinia = createPinia()
    setActivePinia(pinia)
    useSessionStore().user = employeeUser('EMPLOYEE')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
  })

  async function mountView(component: unknown, role: Role) {
    const pinia = createPinia()
    setActivePinia(pinia)
    useSessionStore().user = employeeUser(role)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'home', component: component as never },
        { path: '/employees/:employeeId', name: 'employee-profile', component: defineComponent({ setup: () => () => h('p') }) },
      ],
    })
    await router.push('/')
    await router.isReady()
    const wrapper = mount(component as never, { global: { plugins: [pinia, router] } })
    await flushPromises()
    return wrapper
  }

  it('loads the employee dashboard from /api/dashboard with a named attendance status', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      expect(String(input)).toContain('/api/dashboard')
      return jsonResponse(200, {
        kind: 'EMPLOYEE',
        headline: 'Check in when the workday starts',
        attendance_state: 'not_checked_in',
        leave_balances: [{ leave_type: 'paid', remaining_days: 12 }],
        next_pay_date: '2026-09-05',
        incomplete_profile: false,
      })
    })
    const wrapper = await mountView(DashboardView, 'EMPLOYEE')
    expect(wrapper.text()).toMatch(/Not checked in/i)
    expect(wrapper.text()).toMatch(/Check in/)
    expect(wrapper.text()).toMatch(/2026-09-05/)
    expect(wrapper.html()).not.toMatch(/WorkCard/)
  })

  it('loads the HR dashboard coverage numbers from /api/dashboard', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(200, {
        kind: 'HR',
        headline: "Today's coverage",
        headcount: 2,
        pending_approvals: 0,
        attendance_exceptions: 0,
        payroll_period_due: false,
      }),
    )
    const wrapper = await mountView(DashboardView, 'HR')
    expect(wrapper.text()).toMatch(/Headcount/)
    expect(wrapper.text()).toMatch(/2/)
    expect(wrapper.text()).toMatch(/Pending approvals/)
    expect(wrapper.text()).toMatch(/Queue empty|0/)
  })

  it('renders the people directory as a table from /api/employees', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      expect(String(input)).toContain('/api/employees')
      return jsonResponse(200, [
        {
          id: '33333333-3333-3333-3333-333333333333',
          employee_code: 'EMP-1001',
          first_name: 'Ada',
          last_name: 'Ng',
          status: 'ACTIVE',
          role: 'EMPLOYEE',
        },
      ])
    })
    const wrapper = await mountView(EmployeesView, 'HR')
    const table = wrapper.get('table')
    expect(table.text()).toMatch(/EMP-1001/)
    expect(table.text()).toMatch(/Ada Ng/)
    expect(table.text()).toMatch(/\bActive\b/)
  })

  it('loads attendance from /api/attendance and keeps check-in wired after a 501', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/attendance/check-in') && init?.method === 'POST') {
        return jsonResponse(501, { detail: 'Check-in is not implemented.' })
      }
      expect(url).toContain('/api/attendance')
      return jsonResponse(200, {
        role: 'EMPLOYEE',
        employee_id: '33333333-3333-3333-3333-333333333333',
        sessions: [],
        open_session: null,
        exceptions: [],
      })
    })
    const wrapper = await mountView(AttendanceView, 'EMPLOYEE')
    const checkIn = wrapper.findAll('button').find((node) => node.text().match(/Check in/i))
    expect(checkIn, 'missing Check in action').toBeTruthy()
    expect(checkIn!.attributes('disabled')).toBeUndefined()
    await checkIn!.trigger('click')
    await flushPromises()
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).includes('/api/attendance/check-in') && (init as RequestInit | undefined)?.method === 'POST')).toBe(true)
    expect(wrapper.get('[role="alert"]').text()).toMatch(/not implemented|Check-in/i)
  })

  it('loads time off from /api/time-off as a request table', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      expect(String(input)).toContain('/api/time-off')
      return jsonResponse(200, {
        role: 'EMPLOYEE',
        balances: [{ leave_type: 'paid', remaining_days: 8 }],
        requests: [],
        pending_queue: [],
      })
    })
    const wrapper = await mountView(TimeOffView, 'EMPLOYEE')
    expect(wrapper.get('table').text()).toMatch(/paid/i)
    expect(wrapper.text()).toMatch(/No requests yet|0/)
  })

  it('loads payroll periods from /api/payroll as a table', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      expect(String(input)).toContain('/api/payroll')
      return jsonResponse(200, {
        role: 'EMPLOYEE',
        periods: [
          {
            id: 'p1',
            starts_on: '2026-08-01',
            ends_on: '2026-08-31',
            pay_date: '2026-09-05',
            status: 'PUBLISHED',
          },
        ],
        records: [{ id: 'r1', net_amount: '2400.00', currency: 'USD', published_at: '2026-09-05T00:00:00Z' }],
      })
    })
    const wrapper = await mountView(PayrollView, 'EMPLOYEE')
    expect(wrapper.get('table').text()).toMatch(/2026-08-01/)
    expect(wrapper.get('table').text()).toMatch(/PUBLISHED/)
    expect(wrapper.text()).toMatch(/USD/)
    expect(wrapper.text()).toMatch(/2400/)
  })
})
