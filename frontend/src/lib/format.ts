export function formatLocalIsoDate(value: Date = new Date()): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function formatClock(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(date)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function personLabel(name: string | null | undefined, fallback = 'Unnamed employee'): string {
  const trimmed = name?.trim()
  return trimmed || fallback
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

export function formatCurrency(currency: string, value: string | number | null | undefined): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return `${currency} ${value ?? '—'}`
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount)
}

export function formatEnumLabel(value: string | null | undefined): string {
  if (!value) return 'Not provided'
  return value
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}
