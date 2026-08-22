import { describe, expect, it } from 'vitest'

import router from '@/router'

describe('routes', () => {
  it('registers the implemented route templates without account activation', () => {
    const paths = router.getRoutes().map((route) => route.path)
    expect(paths).toEqual(
      expect.arrayContaining([
        '/sign-in',
        '/dashboard',
        '/employees',
        '/employees/:employeeId',
        '/attendance',
        '/time-off',
        '/payroll',
        '/settings',
      ]),
    )
    expect(paths).not.toContain('/activate-account')
  })
})
