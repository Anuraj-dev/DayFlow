export function countedWorkdays(startsOn: string, endsOn: string): number {
  if (!startsOn || !endsOn) return 0
  const start = Date.parse(`${startsOn}T00:00:00Z`)
  const end = Date.parse(`${endsOn}T00:00:00Z`)
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return 0
  let total = 0
  const cursor = new Date(start)
  const last = new Date(end)
  while (cursor <= last) {
    const weekday = cursor.getUTCDay()
    if (weekday !== 0 && weekday !== 6) total += 1
    cursor.setUTCDate(cursor.getUTCDate() + 1)
  }
  return total
}

export function rangesOverlap(aStart: string, aEnd: string, bStart: string, bEnd: string): boolean {
  return aStart <= bEnd && bStart <= aEnd
}

export function leaveRequiresBalance(leaveType: string): boolean {
  return leaveType.trim().toUpperCase() !== 'UNPAID'
}

export function isBlockingLeaveStatus(status: string): boolean {
  const value = status.trim().toUpperCase()
  return value === 'PENDING' || value === 'APPROVED'
}
