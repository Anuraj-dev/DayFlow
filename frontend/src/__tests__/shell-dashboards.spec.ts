import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { RouterView, createMemoryHistory, createRouter, type Router } from 'vue-router'

import AppShell from '@/layouts/AppShell.vue'
import { formatClock, formatLocalIsoDate } from '@/lib/format'
import { useSessionStore } from '@/stores/session'
import type { AttendanceHome, DashboardPayload, Role, SessionUser } from '@/types/domain'
import DashboardView from '@/views/DashboardView.vue'

type FetchMock = ReturnType<typeof vi.fn>

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

function attendanceHome(
  overrides: Partial<AttendanceHome> = {},
  role: Role = 'EMPLOYEE',
): AttendanceHome {
  return {
    role,
    employee_id: '33333333-3333-3333-3333-333333333333',
    sessions: [],
    open_session: null,
    exceptions: [],
    ...overrides,
  }
}

function employeeDashboard(
  overrides: Partial<Omit<Extract<DashboardPayload, { kind: 'EMPLOYEE' }>, 'kind'>> = {},
): DashboardPayload {
  return {
    kind: 'EMPLOYEE',
    headline: 'Check in when the workday starts',
    attendance_state: 'not_checked_in',
    leave_balances: [{ leave_type: 'paid', remaining_days: 12 }],
    next_pay_date: '2026-09-05',
    incomplete_profile: false,
    ...overrides,
  }
}

function hrDashboard(
  overrides: Partial<Omit<Extract<DashboardPayload, { kind: 'HR' }>, 'kind'>> = {},
): DashboardPayload {
  return {
    kind: 'HR',
    headline: "Today's coverage",
    headcount: 20,
    pending_approvals: 0,
    attendance_exceptions: 0,
    payroll_period_due: false,
    today_coverage: '18 of 20 present',
    ...overrides,
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
            component: defineComponent({ setup: () => () => h('p', 'People') }),
            meta: { title: 'People', hrOnly: true },
          },
          {
            path: 'employees/:employeeId',
            name: 'employee-profile',
            component: defineComponent({ setup: () => () => h('p', 'Profile') }),
            meta: { title: 'Profile' },
          },
          {
            path: 'attendance',
            name: 'attendance',
            component: defineComponent({ setup: () => () => h('p', 'Attendance') }),
            meta: { title: 'Attendance' },
          },
          {
            path: 'time-off',
            name: 'time-off',
            component: defineComponent({ setup: () => () => h('p', 'Time off') }),
            meta: { title: 'Time off' },
          },
          {
            path: 'payroll',
            name: 'payroll',
            component: defineComponent({ setup: () => () => h('p', 'Payroll') }),
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

function panelButton(wrapper: VueWrapper, text: RegExp) {
  const panel = wrapper.get('[data-slot="control-panel"]')
  const button = panel.findAll('button').find((node) => text.test(node.text()))
  expect(button, `missing control panel action matching ${text}`).toBeTruthy()
  return button!
}

function navbarPunch(wrapper: VueWrapper) {
  return wrapper.get('[data-slot="app-navbar"]').get('[data-slot="shell-punch"]')
}

function punchAction(wrapper: VueWrapper, text: RegExp) {
  return navbarPunch(wrapper)
    .findAll('button')
    .find((node) => text.test(node.text()))
}

function isAttendanceHomeUrl(url: string) {
  return url === '/api/attendance' || url.endsWith('/api/attendance')
}

describe('AppShell role nav and control panel', () => {
  let fetchMock: FetchMock
  let wrapper: VueWrapper | null = null

  beforeEach(() => {
    fetchMock = vi.fn(() => jsonResponse(200, employeeDashboard()))
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.clear()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
    document.body.innerHTML = ''
  })

  async function mountShell(
    role: Role,
    dashboard: DashboardPayload,
    attendance: AttendanceHome = attendanceHome({}, role),
    user: SessionUser = employeeUser(role),
  ) {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/attendance/check-in') && init?.method === 'POST') {
        return jsonResponse(501, { detail: 'Check-in is not implemented.' })
      }
      if (url.includes('/api/attendance/check-out') && init?.method === 'POST') {
        return jsonResponse(501, { detail: 'Check-out is not implemented.' })
      }
      if (url.includes('/api/dashboard')) return jsonResponse(200, dashboard)
      if (isAttendanceHomeUrl(url)) return jsonResponse(200, attendance)
      return jsonResponse(404, { detail: 'not found' })
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    useSessionStore().user = user
    sessionStorage.setItem('dayflow.token', 'test-token')
    const router = await makeAppRouter()
    await router.push('/dashboard')
    await router.isReady()
    wrapper = mount(
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

  it('shows Overview, Attendance, Time off, Payroll, and My profile for employees, not People or Settings', async () => {
    const { wrapper: view } = await mountShell('EMPLOYEE', employeeDashboard())
    const nav = view.get('nav[aria-label="Product areas"]')
    expect(nav.text()).toMatch(/Overview/)
    expect(nav.text()).toMatch(/Attendance/)
    expect(nav.text()).toMatch(/Time off/)
    expect(nav.text()).toMatch(/Payroll/)
    expect(nav.text()).not.toMatch(/People/)
    expect(nav.text()).not.toMatch(/Settings/)

    await view.get('[aria-haspopup="menu"]').trigger('click')
    expect(view.get('[role="menu"]').text()).toMatch(/My profile/)
    expect(view.get('[role="menu"]').text()).toMatch(/Log out/)
  })

  it('adds People and Settings for HR', async () => {
    const { wrapper: view } = await mountShell('HR', hrDashboard())
    const nav = view.get('nav[aria-label="Product areas"]')
    expect(nav.text()).toMatch(/Overview/)
    expect(nav.text()).toMatch(/People/)
    expect(nav.text()).toMatch(/Attendance/)
    expect(nav.text()).toMatch(/Time off/)
    expect(nav.text()).toMatch(/Payroll/)
    expect(nav.text()).toMatch(/Settings/)
  })

  it('puts the page action in the control panel', async () => {
    const { wrapper: view } = await mountShell('EMPLOYEE', employeeDashboard())
    expect(panelButton(view, /Check in/i).attributes('disabled')).toBeUndefined()
  })

  it('shows Check out in the 46px bar while open_session is set, with Checked in since from check_in_at', async () => {
    const checkInAt = '2026-08-22T03:30:00Z'
    const { wrapper: view } = await mountShell(
      'EMPLOYEE',
      employeeDashboard({ attendance_state: 'checked_in' }),
      attendanceHome({
        open_session: { id: 's-open', check_in_at: checkInAt },
      }),
    )
    const punch = navbarPunch(view)
    expect(punch.text()).toContain(`Checked in since ${formatClock(checkInAt)}`)
    expect(punchAction(view, /Check out/i)).toBeTruthy()
    expect(punchAction(view, /Check in/i)).toBeUndefined()
  })

  it('does not offer Check out after a successful check-out', async () => {
    const checkInAt = '2026-08-22T03:30:00Z'
    const today = formatLocalIsoDate()
    const openHome = attendanceHome({
      open_session: { id: 's-open', check_in_at: checkInAt },
      sessions: [
        {
          id: 's-open',
          employee_id: '33333333-3333-3333-3333-333333333333',
          work_date: today,
          check_in_at: checkInAt,
          check_out_at: null,
          status: 'OPEN',
        },
      ],
    })
    const closedHome = attendanceHome({
      open_session: null,
      sessions: [
        {
          id: 's-open',
          employee_id: '33333333-3333-3333-3333-333333333333',
          work_date: today,
          check_in_at: checkInAt,
          check_out_at: `${today}T12:00:00Z`,
          status: 'PRESENT',
        },
      ],
    })
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/attendance/check-out') && init?.method === 'POST') {
        return jsonResponse(200, {
          id: 's-open',
          employee_id: '33333333-3333-3333-3333-333333333333',
          work_date: today,
          check_in_at: checkInAt,
          check_out_at: `${today}T12:00:00Z`,
          source: 'SERVER',
          status: 'PRESENT',
          worked_minutes: 510,
        })
      }
      if (url.includes('/api/dashboard')) {
        const checkedOut = fetchMock.mock.calls.some(
          ([called, calledInit]) =>
            String(called).includes('/api/attendance/check-out') &&
            (calledInit as RequestInit | undefined)?.method === 'POST',
        )
        return jsonResponse(
          200,
          employeeDashboard({
            attendance_state: checkedOut ? 'checked_out' : 'checked_in',
          }),
        )
      }
      if (isAttendanceHomeUrl(url)) {
        const checkedOut = fetchMock.mock.calls.some(
          ([called, calledInit]) =>
            String(called).includes('/api/attendance/check-out') &&
            (calledInit as RequestInit | undefined)?.method === 'POST',
        )
        return jsonResponse(200, checkedOut ? closedHome : openHome)
      }
      return jsonResponse(404, { detail: 'not found' })
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    useSessionStore().user = employeeUser('EMPLOYEE')
    sessionStorage.setItem('dayflow.token', 'test-token')
    const router = await makeAppRouter()
    await router.push('/dashboard')
    await router.isReady()
    wrapper = mount(
      defineComponent({
        setup: () => () => h(RouterView),
      }),
      {
        attachTo: document.body,
        global: { plugins: [pinia, router] },
      },
    )
    await flushPromises()

    const checkOut = punchAction(wrapper, /Check out/i)
    expect(checkOut).toBeTruthy()
    await checkOut!.trigger('click')
    await flushPromises()

    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes('/api/attendance/check-out') &&
          (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(true)
    expect(navbarPunch(wrapper).text()).toMatch(/Checked out/)
    expect(punchAction(wrapper, /Check out/i)).toBeUndefined()
  })

  it('shows punch actions for an employee session user, including HR with an employee record', async () => {
    const { wrapper: employeeView } = await mountShell('EMPLOYEE', employeeDashboard())
    expect(navbarPunch(employeeView).text()).toMatch(/Not checked in/)
    expect(punchAction(employeeView, /Check in/i)).toBeTruthy()
    employeeView.unmount()
    wrapper = null

    const { wrapper: hrView } = await mountShell('HR', hrDashboard())
    wrapper = hrView
    expect(navbarPunch(hrView).text()).toMatch(/Not checked in/)
    expect(punchAction(hrView, /Check in/i)).toBeTruthy()
  })

  it('hides the shell punch control when employee_id is null', async () => {
    const { wrapper: view } = await mountShell(
      'HR',
      hrDashboard(),
      attendanceHome({ employee_id: null }, 'HR'),
      { ...employeeUser('HR'), employee_id: null },
    )
    expect(view.find('[data-slot="shell-punch"]').exists()).toBe(false)
    expect(view.text()).not.toMatch(/Not checked in/)
    expect(view.text()).not.toMatch(/Check in/)
  })

  it('shows the API error on a failed shell punch and does not fake success', async () => {
    const { wrapper: view } = await mountShell('EMPLOYEE', employeeDashboard())
    await punchAction(view, /Check in/i)!.trigger('click')
    await flushPromises()
    expect(view.get('[data-slot="shell-punch-error"]').text()).toMatch(/not implemented|Check-in/i)
    expect(navbarPunch(view).text()).toMatch(/Not checked in/)
    expect(punchAction(view, /Check in/i)).toBeTruthy()
    expect(view.text()).not.toMatch(/Checked in successfully/)
  })
})

describe('employee dashboard states', () => {
  let fetchMock: FetchMock
  let wrapper: VueWrapper | null = null

  beforeEach(() => {
    fetchMock = vi.fn(() => jsonResponse(200, employeeDashboard()))
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.clear()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
    document.body.innerHTML = ''
  })

  async function mountDashboard(
    payload: DashboardPayload,
    attendance: AttendanceHome = attendanceHome(),
  ) {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/attendance/check-in') && init?.method === 'POST') {
        return jsonResponse(501, { detail: 'Check-in is not implemented.' })
      }
      if (url.includes('/api/attendance/check-out') && init?.method === 'POST') {
        return jsonResponse(501, { detail: 'Check-out is not implemented.' })
      }
      if (url.includes('/api/dashboard')) return jsonResponse(200, payload)
      if (isAttendanceHomeUrl(url)) return jsonResponse(200, attendance)
      return jsonResponse(404, { detail: 'not found' })
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    useSessionStore().user = employeeUser('EMPLOYEE')
    sessionStorage.setItem('dayflow.token', 'test-token')
    const router = await makeAppRouter()
    await router.push('/dashboard')
    await router.isReady()
    wrapper = mount(
      defineComponent({
        setup: () => () => h(RouterView),
      }),
      {
        attachTo: document.body,
        global: { plugins: [pinia, router] },
      },
    )
    await flushPromises()
    return wrapper
  }

  it('leads with the attendance action when not checked in', async () => {
    const view = await mountDashboard(employeeDashboard())
    expect(view.text()).toMatch(/Not checked in/)
    const headingRow = view.get('.attendance-heading-row')
    expect(headingRow.get('#attendance-heading').text()).toBe('Attendance')
    expect(headingRow.get('[role="status"]').text()).toMatch(/Not checked in/)
    const checkIn = panelButton(view, /Check in/i)
    expect(checkIn.attributes('disabled')).toBeUndefined()
    await checkIn.trigger('click')
    await flushPromises()
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes('/api/attendance/check-in') &&
          (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(true)
    expect(
      view
        .findAll('[role="alert"]')
        .map((node) => node.text())
        .join(' '),
    ).toMatch(/not implemented|Check-in/i)
  })

  it('switches the control action to Check out after check-in', async () => {
    const view = await mountDashboard(
      employeeDashboard({
        headline: 'You are checked in',
        attendance_state: 'checked_in',
      }),
      attendanceHome({
        open_session: { id: 's-open', check_in_at: '2026-08-22T03:30:00Z' },
      }),
    )
    expect(view.text()).toMatch(/Checked in/)
    expect(panelButton(view, /Check in/i).attributes('disabled')).toBeDefined()
    const checkOut = panelButton(view, /Check out/i)
    expect(checkOut.attributes('disabled')).toBeUndefined()
    await checkOut.trigger('click')
    await flushPromises()
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes('/api/attendance/check-out') &&
          (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(true)
  })

  it('disables punches when checked out or on leave and flags an incomplete profile', async () => {
    const checkedOut = await mountDashboard(
      employeeDashboard({
        headline: 'Workday closed',
        attendance_state: 'checked_out',
      }),
    )
    expect(checkedOut.text()).toMatch(/Checked out/)
    expect(panelButton(checkedOut, /Check in/i).attributes('disabled')).toBeDefined()
    expect(panelButton(checkedOut, /Check out/i).attributes('disabled')).toBeDefined()
    checkedOut.unmount()

    wrapper = null
    const onLeave = await mountDashboard(
      employeeDashboard({
        headline: 'Approved leave today',
        attendance_state: 'on_leave',
      }),
    )
    expect(onLeave.text()).toMatch(/On leave/)
    expect(panelButton(onLeave, /Check in/i).attributes('disabled')).toBeDefined()
    onLeave.unmount()

    wrapper = null
    const incomplete = await mountDashboard(
      employeeDashboard({
        incomplete_profile: true,
        headline: 'Complete your profile',
      }),
    )
    expect(incomplete.text()).toMatch(/Incomplete profile/)
    expect(
      incomplete.get('a[href="/employees/33333333-3333-3333-3333-333333333333"]').text(),
    ).toMatch(/My profile/)
  })
})

describe('HR dashboard states', () => {
  let fetchMock: FetchMock
  let wrapper: VueWrapper | null = null

  beforeEach(() => {
    fetchMock = vi.fn(() => jsonResponse(200, hrDashboard()))
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.clear()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
    document.body.innerHTML = ''
  })

  async function mountDashboard(payload: DashboardPayload) {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      if (String(input).includes('/api/dashboard')) return jsonResponse(200, payload)
      if (isAttendanceHomeUrl(String(input))) return jsonResponse(200, attendanceHome({}, 'HR'))
      return jsonResponse(404, { detail: 'not found' })
    })
    const pinia = createPinia()
    setActivePinia(pinia)
    useSessionStore().user = employeeUser('HR')
    sessionStorage.setItem('dayflow.token', 'test-token')
    const router = await makeAppRouter()
    await router.push('/dashboard')
    await router.isReady()
    wrapper = mount(
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

  it('shows headcount, coverage, and an empty approval queue', async () => {
    const { wrapper: view } = await mountDashboard(hrDashboard())
    expect(view.text()).toMatch(/Headcount/)
    expect(view.text()).toMatch(/20/)
    expect(view.text()).toMatch(/Coverage/)
    expect(view.text()).toMatch(/18 of 20 present/)
    expect(view.text()).toMatch(/Pending approvals/)
    expect(view.text()).toMatch(/Queue empty/)
    expect(view.text()).toMatch(/Attendance exceptions/)
  })

  it('flags payroll due and puts Open payroll in the control panel', async () => {
    const { wrapper: view, router } = await mountDashboard(
      hrDashboard({
        pending_approvals: 3,
        attendance_exceptions: 2,
        payroll_period_due: true,
        today_coverage: '16 of 20 present',
      }),
    )
    expect(view.text()).toMatch(/Due/)
    expect(view.text()).toMatch(/Payroll period due/)
    expect(view.text()).not.toMatch(/Queue empty/)
    const action = panelButton(view, /Open payroll/i)
    expect(action.attributes('disabled')).toBeUndefined()
    await action.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('payroll')
  })
})
