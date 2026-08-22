import { describe, expect, it } from 'vitest'

import router from '@/router'

describe('routes', () => {
  it('registers the nine MVP templates', () => {
    const paths = router.getRoutes().map((route) => route.path)
    expect(paths).toEqual(
      expect.arrayContaining([
        '/sign-in',
        '/activate-account',
        '/dashboard',
        '/employees',
        '/employees/:employeeId',
        '/attendance',
        '/time-off',
        '/payroll',
        '/settings',
      ]),
    )
  })
})
