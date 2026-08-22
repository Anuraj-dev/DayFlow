import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'

import AppShell from '@/layouts/AppShell.vue'
import { useSessionStore } from '@/stores/session'
import type { AttendanceHome, Role, SessionUser } from '@/types/domain'
import AttendanceView from '@/views/AttendanceView.vue'

type FetchMock = ReturnType<typeof vi.fn>

const SELF_ID = '33333333-3333-3333-3333-333333333333'

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

function home(overrides: Partial<AttendanceHome> = {}): AttendanceHome {
  return {
    role: 'EMPLOYEE',
    employee_id: SELF_ID,
    sessions: [],
    open_session: null,
    exceptions: [],
    ...overrides,
  }
}

function namedButton(wrapper: VueWrapper, text: string) {
  const button = wrapper.findAll('button').find((node) => node.text().includes(text))
  expect(button, `missing button "${text}"`).toBeTruthy()
  return button!
}

function shellPunchButton(wrapper: VueWrapper, text: RegExp) {
  const shell = wrapper.get('[data-slot="shell-punch"]')
  const button = shell.findAll('button').find((node) => text.test(node.text()))
  expect(button, `missing shell punch action matching ${text}`).toBeTruthy()
  return button!
}

function inputByLabel(wrapper: VueWrapper, labelText: string) {
  const label = wrapper.findAll('label').find((node) => node.text().includes(labelText))
  expect(label, `missing label "${labelText}"`).toBeTruthy()
  const control = label!.find('input, textarea, select')
  expect(control.exists(), `missing field for "${labelText}"`).toBe(true)
  return control
}

async function mountAttendance(role: Role) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useSessionStore().user = sessionUser(role)
  const stub = defineComponent({ setup: () => () => h('p', 'stub') })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        component: AppShell,
        children: [
          {
            path: 'attendance',
            name: 'attendance',
            component: AttendanceView,
            meta: { title: 'Attendance' },
          },
          { path: 'dashboard', name: 'dashboard', component: stub, meta: { title: 'Overview' } },
          { path: 'employees', name: 'employees', component: stub, meta: { title: 'People' } },
          { path: 'time-off', name: 'time-off', component: stub, meta: { title: 'Time off' } },
          { path: 'payroll', name: 'payroll', component: stub, meta: { title: 'Payroll' } },
          { path: 'settings', name: 'settings', component: stub, meta: { title: 'Settings' } },
        ],
      },
    ],
  })
  await router.push('/attendance')
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
  return wrapper
}

describe('Employee attendance', () => {
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

  it('keeps punch actions in the navbar and only shows correction in the control panel', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/attendance/check-in') && init?.method === 'POST') {
        return jsonResponse(200, {
          id: 's-today',
          employee_id: SELF_ID,
          work_date: '2026-08-22',
          check_in_at: '2026-08-22T03:30:00Z',
          check_out_at: null,
          source: 'SERVER',
          status: 'OPEN',
          worked_minutes: null,
        })
      }
      expect(url).toContain('/api/attendance')
      const hasOpen = fetchMock.mock.calls.some(
        ([called, calledInit]) =>
          String(called).includes('/api/attendance/check-in') &&
          (calledInit as RequestInit | undefined)?.method === 'POST',
      )
      return jsonResponse(
        200,
        home({
          open_session: hasOpen ? { id: 's-today', check_in_at: '2026-08-22T03:30:00Z' } : null,
          sessions: hasOpen
            ? [
                {
                  id: 's-today',
                  work_date: '2026-08-22',
                  check_in_at: '2026-08-22T03:30:00Z',
                  check_out_at: null,
                  status: 'OPEN',
                },
              ]
            : [],
        }),
      )
    })

    const wrapper = await mountAttendance('EMPLOYEE')
    const checkIn = shellPunchButton(wrapper, /Check in/i)
    const controlPanel = document.querySelector('[data-slot="control-panel"]')
    expect(controlPanel?.textContent).toMatch(/Request correction/i)
    expect(controlPanel?.textContent).not.toMatch(/Check in|Check out/i)

    await checkIn.trigger('click')
    await flushPromises()

    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes('/api/attendance/check-in') && (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(true)
    expect(shellPunchButton(wrapper, /Check out/i)).toBeTruthy()
    expect(wrapper.text()).toMatch(/Checked in/i)
  })

  it('lists the selected month with present, late, missing check-out, leave, half-day, and correction requested', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(
        200,
        home({
          month: '2026-08',
          full_day_minutes: 480,
          summary: { days_present: 2.5, leave_days: 1, scheduled_working_days: 21 },
          sessions: [
            {
              id: 's-present',
              work_date: '2026-08-21',
              check_in_at: '2026-08-21T03:30:00Z',
              check_out_at: '2026-08-21T12:30:00Z',
              status: 'PRESENT',
            },
            {
              id: 's-late',
              work_date: '2026-08-20',
              check_in_at: '2026-08-20T04:45:00Z',
              check_out_at: '2026-08-20T13:00:00Z',
              status: 'LATE',
            },
            {
              id: 's-open',
              work_date: '2026-08-19',
              check_in_at: '2026-08-19T03:31:00Z',
              check_out_at: null,
              status: 'OPEN',
            },
            {
              id: 's-leave',
              work_date: '2026-08-18',
              check_in_at: null,
              check_out_at: null,
              status: 'LEAVE',
            },
            {
              id: 's-half',
              work_date: '2026-08-17',
              check_in_at: '2026-08-17T03:30:00Z',
              check_out_at: '2026-08-17T08:00:00Z',
              status: 'HALF_DAY',
            },
            {
              id: 's-corr',
              work_date: '2026-08-16',
              check_in_at: '2026-08-16T03:30:00Z',
              check_out_at: '2026-08-16T12:00:00Z',
              status: 'PRESENT',
              correction_status: 'PENDING',
            },
          ],
        }),
      ),
    )

    const wrapper = await mountAttendance('EMPLOYEE')
    const table = wrapper.get('table')
    expect(table.text()).toMatch(/Work date/)
    expect(wrapper.text()).toMatch(/August 2026|2026-08/)
    expect(wrapper.text()).toMatch(/Days present/)
    expect(wrapper.text()).toMatch(/Leave days/)
    expect(wrapper.text()).toMatch(/Scheduled working days/)
    expect(wrapper.text()).toMatch(/Work hours/)
    expect(wrapper.text()).toMatch(/Extra hours/)
    expect(wrapper.text()).toMatch(/Present/)
    expect(wrapper.text()).toMatch(/Late/)
    expect(wrapper.text()).toMatch(/Missing check-out/)
    expect(wrapper.text()).toMatch(/Leave|On leave/)
    expect(wrapper.text()).toMatch(/Half-day/)

    const tones = wrapper.findAll('[data-tone]').map((node) => ({
      text: node.text().trim(),
      tone: node.attributes('data-tone'),
    }))
    expect(tones.some((row) => row.text === 'Present' && row.tone === 'confirmed')).toBe(true)
    expect(tones.some((row) => row.text === 'Late' && row.tone === 'review')).toBe(true)
    expect(tones.some((row) => row.text === 'Missing check-out' && row.tone === 'danger')).toBe(true)
    expect(tones.some((row) => /leave/i.test(row.text) && row.tone)).toBe(true)
    expect(tones.some((row) => row.text === 'Half-day' && row.tone === 'review')).toBe(true)
    expect(tones.some((row) => row.text === 'Correction requested' && row.tone === 'review')).toBe(true)
  })

  it('keeps request-correction wired when POST /api/attendance/corrections returns 501', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/attendance/corrections') && init?.method === 'POST') {
        return jsonResponse(501, { detail: 'Corrections are not implemented.' })
      }
      return jsonResponse(
        200,
        home({
          sessions: [
            {
              id: 's-present',
              work_date: '2026-08-21',
              check_in_at: '2026-08-21T03:30:00Z',
              check_out_at: '2026-08-21T12:30:00Z',
              status: 'PRESENT',
            },
          ],
        }),
      )
    })

    const wrapper = await mountAttendance('EMPLOYEE')
    await namedButton(wrapper, 'Request correction').trigger('click')
    await nextTick()
    await inputByLabel(wrapper, 'Reason').setValue('Forgot to check out on time.')
    await namedButton(wrapper, 'Submit correction').trigger('click')
    await flushPromises()

    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url).includes('/api/attendance/corrections') && (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(true)
    expect(wrapper.get('[role="alert"]').text()).toMatch(/not implemented|correction/i)
  })

  it('requests another month from the month navigator', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      const month = url.includes('month=2026-07') ? '2026-07' : '2026-08'
      return jsonResponse(
        200,
        home({
          month,
          summary: { days_present: month === '2026-07' ? 18 : 3.5, leave_days: 1, scheduled_working_days: 22 },
          days: [
            {
              work_date: `${month}-03`,
              check_in_at: `${month}-03T03:30:00Z`,
              check_out_at: `${month}-03T12:30:00Z`,
              worked_minutes: 540,
              extra_minutes: 60,
              status: 'PRESENT',
            },
          ],
        }),
      )
    })

    const wrapper = await mountAttendance('EMPLOYEE')
    expect(wrapper.text()).toMatch(/August 2026|2026-08/)
    await inputByLabel(wrapper, 'Month').setValue('2026-07')
    await flushPromises()
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('month=2026-07'))).toBe(true)
    expect(wrapper.text()).toMatch(/July 2026|2026-07/)
  })
})

describe('HR attendance review', () => {
  let fetchMock: FetchMock

  beforeEach(() => {
    fetchMock = vi.fn(() => jsonResponse(200, home({ role: 'HR' })))
    vi.stubGlobal('fetch', fetchMock)
    sessionStorage.setItem('dayflow.token', 'test-token')
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    sessionStorage.clear()
    document.body.innerHTML = ''
  })

  it('renders a filterable exception table for missing check-out and corrections', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(
        200,
        home({
          role: 'HR',
          exceptions: [
            {
              id: 'ex-open',
              employee_id: SELF_ID,
              employee_name: 'Rohan Iyer',
              kind: 'missing_check_out',
              status: 'OPEN',
            },
            {
              id: 'ex-corr',
              employee_id: '44444444-4444-4444-4444-444444444444',
              employee_name: 'Nia Shah',
              kind: 'correction_pending',
              status: 'PENDING',
            },
          ],
        }),
      ),
    )

    const wrapper = await mountAttendance('HR')
    const table = wrapper.get('table')
    expect(table.text()).toMatch(/Rohan Iyer/)
    expect(table.text()).toMatch(/Missing check-out/)
    expect(table.text()).toMatch(/Nia Shah/)
    expect(table.text()).toMatch(/Correction requested/)
    const statuses = wrapper.findAll('[data-tone]').map((node) => node.text().trim())
    expect(statuses).toContain('Missing check-out')
    expect(statuses.some((text) => /Correction requested|Pending/i.test(text))).toBe(true)

    await inputByLabel(wrapper, 'Exception').setValue('missing_check_out')
    await nextTick()
    expect(wrapper.get('table').text()).toMatch(/Rohan Iyer/)
    expect(wrapper.get('table').text()).not.toMatch(/Nia Shah/)

    await inputByLabel(wrapper, 'Exception').setValue('correction_pending')
    await nextTick()
    expect(wrapper.get('table').text()).toMatch(/Nia Shah/)
    expect(wrapper.get('table').text()).not.toMatch(/Rohan Iyer/)
    expect(wrapper.text()).not.toMatch(/This week/)
    expect(wrapper.text()).toMatch(/Today/)
  })

  it('renders today roster plus the existing exception queue', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(
        200,
        home({
          role: 'HR',
          today: '2026-08-22',
          roster: [
            {
              employee_id: SELF_ID,
              employee_name: 'Rohan Iyer',
              check_in_at: '2026-08-22T03:30:00Z',
              check_out_at: '2026-08-22T12:30:00Z',
              worked_minutes: 540,
              extra_minutes: 60,
              status: 'PRESENT',
            },
          ],
          exceptions: [
            {
              id: 'ex-open',
              employee_id: SELF_ID,
              employee_name: 'Rohan Iyer',
              kind: 'missing_check_out',
              status: 'OPEN',
            },
          ],
        }),
      ),
    )

    const wrapper = await mountAttendance('HR')
    const tables = wrapper.findAll('table')
    expect(tables.length).toBeGreaterThan(0)
    expect(tables[0]?.text()).toMatch(/Rohan Iyer/)
    expect(tables[0]?.text()).toMatch(/Present/)
    expect(wrapper.text()).toMatch(/Today/)
    expect(wrapper.text()).toMatch(/Missing check-out/)
  })

  it('shows correction evidence and sends an HR approval', async () => {
    let reviewed = false
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/attendance/corrections/ex-corr/review') && init?.method === 'POST') {
        reviewed = true
        return jsonResponse(200, { id: 'ex-corr', status: 'APPROVED' })
      }
      return jsonResponse(
        200,
        home({
          role: 'HR',
          exceptions: reviewed
            ? []
            : [
                {
                  id: 'ex-corr',
                  employee_id: SELF_ID,
                  employee_name: 'Rohan Iyer',
                  kind: 'correction_pending',
                  status: 'PENDING',
                  work_date: '2026-08-20',
                  current_check_in_at: '2026-08-20T04:00:00Z',
                  current_check_out_at: '2026-08-20T12:00:00Z',
                  proposed_check_in_at: '2026-08-20T03:30:00Z',
                  proposed_check_out_at: '2026-08-20T12:30:00Z',
                  reason: 'Badge log shows an earlier arrival.',
                },
              ],
        }),
      )
    })

    const wrapper = await mountAttendance('HR')
    expect(wrapper.text()).toMatch(/Badge log shows an earlier arrival/)
    expect(wrapper.text()).toMatch(/Proposed check in/)
    await namedButton(wrapper, 'Approve correction').trigger('click')
    await flushPromises()

    const reviewCall = fetchMock.mock.calls.find(([url]) =>
      String(url).includes('/api/attendance/corrections/ex-corr/review'),
    )
    expect(reviewCall).toBeTruthy()
    expect(JSON.parse(String((reviewCall?.[1] as RequestInit).body))).toEqual({
      decision: 'APPROVED',
      comment: null,
    })
    expect(wrapper.text()).toMatch(/Correction approved and attendance updated/)
  })
})
