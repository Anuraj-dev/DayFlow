import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'

import AppShell from '@/layouts/AppShell.vue'
import { useSessionStore } from '@/stores/session'
import type { LeaveRequest, Role, SessionUser, TimeOffHome } from '@/types/domain'
import TimeOffView from '@/views/TimeOffView.vue'

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

function leaveRequest(overrides: Partial<LeaveRequest> = {}): LeaveRequest {
  return {
    id: 'req-1',
    employee_id: SELF_ID,
    leave_type: 'PAID',
    starts_on: '2026-09-07',
    ends_on: '2026-09-09',
    counted_days: 3,
    reason: 'Family visit.',
    status: 'PENDING',
    employee_name: 'Rohan Iyer',
    review_comment: null,
    ...overrides,
  }
}

function home(overrides: Partial<TimeOffHome> = {}): TimeOffHome {
  return {
    role: 'EMPLOYEE',
    employee_id: SELF_ID,
    balances: [
      { leave_type: 'PAID', remaining_days: 18, granted_days: 18, used_days: 0 },
      { leave_type: 'SICK', remaining_days: 8, granted_days: 8, used_days: 0 },
      { leave_type: 'UNPAID', remaining_days: 0, granted_days: 0, used_days: 0 },
    ],
    requests: [],
    pending_queue: [],
    ...overrides,
  }
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

async function fillRequest(
  wrapper: VueWrapper,
  values: { type?: string; starts: string; ends: string; reason?: string },
) {
  await inputByLabel(wrapper, 'Leave type').setValue(values.type ?? 'PAID')
  await inputByLabel(wrapper, 'Starts on').setValue(values.starts)
  await inputByLabel(wrapper, 'Ends on').setValue(values.ends)
  if (values.reason !== undefined) {
    await inputByLabel(wrapper, 'Reason').setValue(values.reason)
  }
  await nextTick()
}

async function mountTimeOff(role: Role) {
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
            path: 'time-off',
            name: 'time-off',
            component: TimeOffView,
            meta: { title: 'Time off' },
          },
          { path: 'dashboard', name: 'dashboard', component: stub, meta: { title: 'Overview' } },
          { path: 'employees', name: 'employees', component: stub, meta: { title: 'People' } },
          { path: 'attendance', name: 'attendance', component: stub, meta: { title: 'Attendance' } },
          { path: 'payroll', name: 'payroll', component: stub, meta: { title: 'Payroll' } },
          { path: 'settings', name: 'settings', component: stub, meta: { title: 'Settings' } },
        ],
      },
    ],
  })
  await router.push('/time-off')
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

describe('Employee time off', () => {
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

  it('shows balances and a labeled request form', async () => {
    const wrapper = await mountTimeOff('EMPLOYEE')
    expect(wrapper.text()).toMatch(/Time off/)
    expect(wrapper.text()).toMatch(/PAID|Paid/)
    expect(wrapper.text()).toMatch(/18/)
    expect(wrapper.text()).toMatch(/SICK|Sick/)
    expect(wrapper.text()).toMatch(/UNPAID|Unpaid/)
    expect(inputByLabel(wrapper, 'Leave type').exists()).toBe(true)
    expect(inputByLabel(wrapper, 'Starts on').exists()).toBe(true)
    expect(inputByLabel(wrapper, 'Ends on').exists()).toBe(true)
    expect(inputByLabel(wrapper, 'Reason').exists()).toBe(true)
    expect(namedButton(wrapper, 'Submit request').exists()).toBe(true)
    expect(wrapper.text()).not.toMatch(/Pending queue/)
    expect(wrapper.text()).not.toMatch(/\bApprove\b/)
  })

  it('treats an unsaved range as a draft and shows counted workdays', async () => {
    const wrapper = await mountTimeOff('EMPLOYEE')
    await fillRequest(wrapper, {
      starts: '2026-08-24',
      ends: '2026-08-26',
      reason: 'Need three workdays.',
    })

    expect(wrapper.text()).toMatch(/Draft/)
    expect(wrapper.text()).toMatch(/3 counted days|Counted days:\s*3/i)
    const tones = wrapper.findAll('[data-tone]').map((node) => ({
      text: node.text().trim(),
      tone: node.attributes('data-tone'),
    }))
    expect(tones.some((row) => row.text === 'Draft' && row.tone === 'review')).toBe(true)
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) => String(url).includes('/api/time-off/requests') && (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(false)
  })

  it('blocks submit and shows overlap when the range overlaps pending or approved leave', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(
        200,
        home({
          requests: [leaveRequest({ status: 'PENDING', starts_on: '2026-09-07', ends_on: '2026-09-09' })],
        }),
      ),
    )

    const wrapper = await mountTimeOff('EMPLOYEE')
    await fillRequest(wrapper, {
      starts: '2026-09-09',
      ends: '2026-09-11',
      reason: 'Overlaps the pending request.',
    })

    expect(wrapper.text()).toMatch(/Overlap/)
    expect(namedButton(wrapper, 'Submit request').attributes('disabled')).toBeDefined()
    await namedButton(wrapper, 'Submit request').trigger('click')
    await flushPromises()
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) => String(url).includes('/api/time-off/requests') && (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(false)
  })

  it('blocks submit and shows insufficient balance when counted days exceed remaining', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(
        200,
        home({
          balances: [
            { leave_type: 'PAID', remaining_days: 2, granted_days: 18, used_days: 16 },
            { leave_type: 'SICK', remaining_days: 8, granted_days: 8, used_days: 0 },
            { leave_type: 'UNPAID', remaining_days: 0, granted_days: 0, used_days: 0 },
          ],
        }),
      ),
    )

    const wrapper = await mountTimeOff('EMPLOYEE')
    await fillRequest(wrapper, {
      type: 'PAID',
      starts: '2026-01-05',
      ends: '2026-01-09',
      reason: 'More paid days than remaining.',
    })

    expect(wrapper.text()).toMatch(/Insufficient balance/)
    expect(namedButton(wrapper, 'Submit request').attributes('disabled')).toBeDefined()
  })

  it('POSTs /api/time-off/requests and lists pending, approved, and rejected with status text', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/time-off/requests') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body)) as {
          leave_type: string
          starts_on: string
          ends_on: string
          reason: string
        }
        expect(body.leave_type).toBe('PAID')
        expect(body.starts_on).toBe('2026-08-24')
        expect(body.ends_on).toBe('2026-08-26')
        expect(body.reason).toMatch(/three workdays/i)
        return jsonResponse(200, leaveRequest({ id: 'req-new', starts_on: body.starts_on, ends_on: body.ends_on, counted_days: 3, status: 'PENDING' }))
      }
      const submitted = fetchMock.mock.calls.some(
        ([called, calledInit]) =>
          String(called).includes('/api/time-off/requests') &&
          !String(called).includes('/cancel') &&
          (calledInit as RequestInit | undefined)?.method === 'POST',
      )
      return jsonResponse(
        200,
        home({
          requests: submitted
            ? [
                leaveRequest({ id: 'req-new', starts_on: '2026-08-24', ends_on: '2026-08-26', status: 'PENDING' }),
                leaveRequest({ id: 'req-ok', starts_on: '2026-07-06', ends_on: '2026-07-07', status: 'APPROVED' }),
                leaveRequest({
                  id: 'req-no',
                  starts_on: '2026-06-01',
                  ends_on: '2026-06-02',
                  status: 'REJECTED',
                  review_comment: 'Team already short that week.',
                }),
              ]
            : [
                leaveRequest({ id: 'req-ok', starts_on: '2026-07-06', ends_on: '2026-07-07', status: 'APPROVED' }),
                leaveRequest({
                  id: 'req-no',
                  starts_on: '2026-06-01',
                  ends_on: '2026-06-02',
                  status: 'REJECTED',
                  review_comment: 'Team already short that week.',
                }),
              ],
        }),
      )
    })

    const wrapper = await mountTimeOff('EMPLOYEE')
    expect(wrapper.text()).toMatch(/Approved/)
    expect(wrapper.text()).toMatch(/Rejected/)
    const before = wrapper.findAll('[data-tone]').map((node) => ({
      text: node.text().trim(),
      tone: node.attributes('data-tone'),
    }))
    expect(before.some((row) => row.text === 'Approved' && row.tone === 'confirmed')).toBe(true)
    expect(before.some((row) => row.text === 'Rejected' && row.tone === 'danger')).toBe(true)

    await fillRequest(wrapper, {
      starts: '2026-08-24',
      ends: '2026-08-26',
      reason: 'Need three workdays.',
    })
    await namedButton(wrapper, 'Submit request').trigger('click')
    await flushPromises()

    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url) === '/api/time-off/requests' && (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(true)
    expect(wrapper.text()).toMatch(/Pending/)
    const after = wrapper.findAll('[data-tone]').map((node) => ({
      text: node.text().trim(),
      tone: node.attributes('data-tone'),
    }))
    expect(after.some((row) => row.text === 'Pending' && row.tone === 'review')).toBe(true)
  })

  it('keeps submit wired when POST /api/time-off/requests returns overlap 409', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/time-off/requests') && init?.method === 'POST') {
        return jsonResponse(409, { detail: 'Leave range overlaps a pending or approved request.' })
      }
      return jsonResponse(200, home())
    })

    const wrapper = await mountTimeOff('EMPLOYEE')
    await fillRequest(wrapper, {
      starts: '2026-10-05',
      ends: '2026-10-06',
      reason: 'Server still owns overlap.',
    })
    await namedButton(wrapper, 'Submit request').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toMatch(/overlap/i)
  })
})

describe('HR leave approvals', () => {
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

  it('renders a pending table with employee, type, dates, and counted days', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(
        200,
        home({
          role: 'HR',
          pending_queue: [
            leaveRequest({
              id: 'req-pending',
              employee_name: 'Rohan Iyer',
              leave_type: 'PAID',
              starts_on: '2026-11-02',
              ends_on: '2026-11-04',
              counted_days: 3,
            }),
          ],
        }),
      ),
    )

    const wrapper = await mountTimeOff('HR')
    expect(wrapper.text()).toMatch(/Leave approvals|Pending/)
    const table = wrapper.get('table')
    expect(table.text()).toMatch(/Rohan Iyer/)
    expect(table.text()).toMatch(/PAID|Paid/)
    expect(table.text()).toMatch(/2026-11-02/)
    expect(table.text()).toMatch(/2026-11-04/)
    expect(table.text()).toMatch(/3/)
    expect(namedButton(wrapper, 'Approve').exists()).toBe(true)
    expect(namedButton(wrapper, 'Reject').exists()).toBe(true)
    expect(wrapper.text()).not.toMatch(/Submit request/)
  })

  it('approves a pending request through POST /api/time-off/requests/:id/approve', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/approve') && init?.method === 'POST') {
        return jsonResponse(200, leaveRequest({ id: 'req-pending', status: 'APPROVED' }))
      }
      const approved = fetchMock.mock.calls.some(
        ([called, calledInit]) =>
          String(called).includes('/approve') && (calledInit as RequestInit | undefined)?.method === 'POST',
      )
      return jsonResponse(
        200,
        home({
          role: 'HR',
          pending_queue: approved
            ? []
            : [leaveRequest({ id: 'req-pending', employee_name: 'Rohan Iyer', status: 'PENDING' })],
        }),
      )
    })

    const wrapper = await mountTimeOff('HR')
    await namedButton(wrapper, 'Approve').trigger('click')
    await flushPromises()

    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url) === '/api/time-off/requests/req-pending/approve' &&
          (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(true)
    expect(wrapper.text()).toMatch(/No pending requests/)
  })

  it('requires a review comment before reject and then POSTs reject', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/reject') && init?.method === 'POST') {
        const body = JSON.parse(String(init.body ?? '{}')) as { comment?: string }
        expect(body.comment).toMatch(/Team already short/i)
        return jsonResponse(200, leaveRequest({ id: 'req-pending', status: 'REJECTED', review_comment: body.comment }))
      }
      const rejected = fetchMock.mock.calls.some(
        ([called, calledInit]) =>
          String(called).includes('/reject') && (calledInit as RequestInit | undefined)?.method === 'POST',
      )
      return jsonResponse(
        200,
        home({
          role: 'HR',
          pending_queue: rejected ? [] : [leaveRequest({ id: 'req-pending', employee_name: 'Rohan Iyer' })],
        }),
      )
    })

    const wrapper = await mountTimeOff('HR')
    await namedButton(wrapper, 'Reject').trigger('click')
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toMatch(/comment/i)
    expect(
      fetchMock.mock.calls.some(
        ([url, init]) => String(url).includes('/reject') && (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(false)

    await inputByLabel(wrapper, 'Review comment').setValue('Team already short that week.')
    await namedButton(wrapper, 'Reject').trigger('click')
    await flushPromises()

    expect(
      fetchMock.mock.calls.some(
        ([url, init]) =>
          String(url) === '/api/time-off/requests/req-pending/reject' &&
          (init as RequestInit | undefined)?.method === 'POST',
      ),
    ).toBe(true)
    expect(wrapper.text()).toMatch(/No pending requests/)
  })

  it('shows a conflict warning when a pending request overlaps another blocking request', async () => {
    fetchMock.mockImplementation(() =>
      jsonResponse(
        200,
        home({
          role: 'HR',
          pending_queue: [
            leaveRequest({
              id: 'req-a',
              employee_id: SELF_ID,
              employee_name: 'Rohan Iyer',
              starts_on: '2026-09-07',
              ends_on: '2026-09-09',
              status: 'PENDING',
            }),
          ],
          requests: [
            leaveRequest({
              id: 'req-a',
              employee_id: SELF_ID,
              employee_name: 'Rohan Iyer',
              starts_on: '2026-09-07',
              ends_on: '2026-09-09',
              status: 'PENDING',
            }),
            leaveRequest({
              id: 'req-b',
              employee_id: SELF_ID,
              employee_name: 'Rohan Iyer',
              starts_on: '2026-09-09',
              ends_on: '2026-09-11',
              status: 'APPROVED',
            }),
            leaveRequest({
              id: 'req-other',
              employee_id: OTHER_ID,
              employee_name: 'Nia Shah',
              starts_on: '2026-09-07',
              ends_on: '2026-09-09',
              status: 'PENDING',
            }),
          ],
        }),
      ),
    )

    const wrapper = await mountTimeOff('HR')
    expect(wrapper.text()).toMatch(/Conflict/)
    expect(wrapper.text()).toMatch(/overlap/i)
  })
})
