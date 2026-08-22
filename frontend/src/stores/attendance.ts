import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api, HttpError } from '@/api/client'
import { formatClock, formatLocalIsoDate } from '@/lib/format'
import { useSessionStore } from '@/stores/session'
import type { AttendanceHome, AttendanceSession } from '@/types/domain'

function sessionWorkDate(row: AttendanceSession): string | null {
  if (row.work_date) return row.work_date
  const stamp = row.check_out_at ?? row.check_in_at
  if (!stamp) return null
  const date = new Date(stamp)
  return Number.isNaN(date.getTime()) ? null : formatLocalIsoDate(date)
}

function normalizeHome(payload: AttendanceHome): AttendanceHome {
  return {
    role: payload.role,
    employee_id: payload.employee_id ?? null,
    sessions: payload.sessions ?? [],
    open_session: payload.open_session ?? null,
    exceptions: payload.exceptions ?? [],
  }
}

export const useAttendanceStore = defineStore('attendance', () => {
  const session = useSessionStore()
  const home = ref<AttendanceHome | null>(null)
  const loading = ref(false)
  const error = ref('')
  const actionError = ref('')
  const punching = ref(false)
  const revision = ref(0)
  let inflight: Promise<void> | null = null

  const employeeId = computed(() => session.user?.employee_id ?? null)
  const visible = computed(() => Boolean(employeeId.value))
  const openSession = computed(() => home.value?.open_session ?? null)

  const mySessions = computed(() => {
    const rows = home.value?.sessions ?? []
    const id = employeeId.value
    if (!id) return rows
    return rows.filter((row) => !row.employee_id || row.employee_id === id)
  })

  const closedToday = computed(() => {
    const today = formatLocalIsoDate()
    return mySessions.value.some((row) => Boolean(row.check_out_at) && sessionWorkDate(row) === today)
  })

  const punchState = computed<'not_checked_in' | 'checked_in' | 'checked_out'>(() => {
    if (openSession.value) return 'checked_in'
    if (closedToday.value) return 'checked_out'
    return 'not_checked_in'
  })

  const statusLabel = computed(() => {
    if (punchState.value === 'checked_in' && openSession.value) {
      return `Checked in since ${formatClock(openSession.value.check_in_at)}`
    }
    if (punchState.value === 'checked_out') return 'Checked out'
    return 'Not checked in'
  })

  const canCheckIn = computed(() => visible.value && punchState.value === 'not_checked_in')
  const canCheckOut = computed(() => visible.value && punchState.value === 'checked_in')

  async function load(): Promise<void> {
    if (!employeeId.value) {
      home.value = null
      return
    }
    if (inflight) return inflight
    inflight = (async () => {
      loading.value = true
      error.value = ''
      try {
        const payload = await api<AttendanceHome>('/api/attendance')
        home.value = normalizeHome(payload)
        revision.value += 1
      } catch (err) {
        error.value = err instanceof Error ? err.message : 'Could not load attendance.'
      } finally {
        loading.value = false
        inflight = null
      }
    })()
    return inflight
  }

  async function punch(path: '/api/attendance/check-in' | '/api/attendance/check-out'): Promise<void> {
    actionError.value = ''
    punching.value = true
    try {
      await api(path, { method: 'POST' })
      inflight = null
      await load()
    } catch (err) {
      actionError.value = err instanceof HttpError ? err.detail : 'Attendance action failed.'
      throw err
    } finally {
      punching.value = false
    }
  }

  function reset(): void {
    home.value = null
    loading.value = false
    error.value = ''
    actionError.value = ''
    punching.value = false
    revision.value = 0
    inflight = null
  }

  return {
    home,
    loading,
    error,
    actionError,
    punching,
    revision,
    visible,
    openSession,
    punchState,
    statusLabel,
    canCheckIn,
    canCheckOut,
    load,
    punch,
    reset,
  }
})
