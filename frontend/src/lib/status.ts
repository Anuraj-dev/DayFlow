function normalizeStatus(state: string | null | undefined): string {
  return (state ?? '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
}

export function attendanceStatusLabel(state: string | null | undefined): string {
  switch (normalizeStatus(state)) {
    case 'not_checked_in':
      return 'Not checked in'
    case 'checked_in':
      return 'Checked in'
    case 'checked_out':
      return 'Checked out'
    case 'on_leave':
    case 'leave':
      return 'On leave'
    case 'present':
      return 'Present'
    case 'late':
      return 'Late'
    case 'half_day':
      return 'Half-day'
    case 'open':
    case 'missing_check_out':
      return 'Missing check-out'
    case 'absent':
      return 'Absent'
    case 'pending':
    case 'correction_pending':
    case 'correction_requested':
      return 'Correction requested'
    case 'approved':
      return 'Approved'
    case 'rejected':
      return 'Rejected'
    default:
      return state ? state.replace(/_/g, ' ') : 'Unknown'
  }
}

export function exceptionKindLabel(kind: string | null | undefined): string {
  switch (normalizeStatus(kind)) {
    case 'missing_check_out':
      return 'Missing check-out'
    case 'correction_pending':
    case 'correction_requested':
      return 'Correction requested'
    default:
      return attendanceStatusLabel(kind)
  }
}

export function leaveTypeLabel(type: string | null | undefined): string {
  switch (normalizeStatus(type)) {
    case 'paid':
      return 'Paid'
    case 'sick':
      return 'Sick'
    case 'unpaid':
      return 'Unpaid'
    default:
      return type ? type.replace(/_/g, ' ') : 'Unknown'
  }
}

export function leaveStatusLabel(status: string | null | undefined): string {
  switch (normalizeStatus(status)) {
    case 'draft':
      return 'Draft'
    case 'pending':
      return 'Pending'
    case 'approved':
      return 'Approved'
    case 'rejected':
      return 'Rejected'
    case 'cancelled':
      return 'Cancelled'
    case 'overlap':
      return 'Overlap'
    case 'insufficient':
    case 'insufficient_balance':
      return 'Insufficient balance'
    default:
      return status ? status.replace(/_/g, ' ') : 'Unknown'
  }
}

export function employeeStatusLabel(status: string | null | undefined): string {
  switch (status) {
    case 'ACTIVE':
      return 'Active'
    case 'INACTIVE':
      return 'Inactive'
    case 'INVITED':
      return 'Invited'
    default:
      return status ? status.replace(/_/g, ' ') : 'Unknown'
  }
}

export function payrollStatusLabel(status: string | null | undefined): string {
  switch (normalizeStatus(status)) {
    case 'draft':
      return 'Draft'
    case 'finalized':
      return 'Finalized'
    case 'published':
      return 'Published'
    case 'validation_errors':
    case 'validation_error':
      return 'Validation errors'
    case 'correction_needed':
      return 'Correction needed'
    default:
      return status ? status.replace(/_/g, ' ') : 'Unknown'
  }
}

export function statusTone(label: string): 'neutral' | 'confirmed' | 'review' | 'danger' {
  const value = label.toLowerCase()
  if (['active', 'approved', 'published', 'present', 'checked in', 'checked out'].includes(value)) {
    return 'confirmed'
  }
  if (
    [
      'rejected',
      'locked',
      'danger',
      'missing check-out',
      'inactive',
      'missing document',
      'insufficient balance',
      'overlap',
      'validation errors',
      'correction needed',
    ].includes(value)
  ) {
    return 'danger'
  }
  if (
    [
      'pending',
      'draft',
      'invited',
      'not checked in',
      'review',
      'unsaved changes',
      'late',
      'half-day',
      'correction requested',
      'conflict',
      'finalized',
    ].includes(value)
  ) {
    return 'review'
  }
  return 'neutral'
}
