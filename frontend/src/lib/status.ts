export function attendanceStatusLabel(state: string | null | undefined): string {
  switch (state) {
    case 'not_checked_in':
      return 'Not checked in'
    case 'checked_in':
      return 'Checked in'
    case 'checked_out':
      return 'Checked out'
    case 'on_leave':
      return 'On leave'
    case 'present':
      return 'Present'
    case 'late':
      return 'Late'
    case 'half_day':
      return 'Half-day'
    case 'missing_check_out':
      return 'Missing check-out'
    default:
      return state ? state.replace(/_/g, ' ') : 'Unknown'
  }
}

export function statusTone(label: string): 'neutral' | 'confirmed' | 'review' | 'danger' {
  const value = label.toLowerCase()
  if (['active', 'approved', 'published', 'present', 'checked in', 'checked out', 'staffed', 'on track', 'clear', 'queue empty'].includes(value)) {
    return 'confirmed'
  }
  if (['rejected', 'locked', 'danger', 'missing check-out'].includes(value)) {
    return 'danger'
  }
  if (['pending', 'draft', 'invited', 'not checked in', 'on leave', 'review', 'due', 'needs review'].includes(value)) {
    return 'review'
  }
  return 'neutral'
}
