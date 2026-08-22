import { createRouter, createWebHistory } from 'vue-router'

import { getToken } from '@/api/client'
import { useSessionStore } from '@/stores/session'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/sign-in',
      name: 'sign-in',
      component: () => import('@/views/SignInView.vue'),
      meta: { public: true, title: 'Sign in' },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppShell.vue'),
      children: [
        { path: '', redirect: '/dashboard' },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: 'Overview' },
        },
        {
          path: 'employees',
          name: 'employees',
          component: () => import('@/views/EmployeesView.vue'),
          meta: { title: 'People', hrOnly: true },
        },
        {
          path: 'employees/:employeeId',
          name: 'employee-profile',
          component: () => import('@/views/EmployeeProfileView.vue'),
          meta: { title: 'Profile' },
        },
        {
          path: 'attendance',
          name: 'attendance',
          component: () => import('@/views/AttendanceView.vue'),
          meta: { title: 'Attendance' },
        },
        {
          path: 'time-off',
          name: 'time-off',
          component: () => import('@/views/TimeOffView.vue'),
          meta: { title: 'Time off' },
        },
        {
          path: 'payroll',
          name: 'payroll',
          component: () => import('@/views/PayrollView.vue'),
          meta: { title: 'Payroll' },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/SettingsView.vue'),
          meta: { title: 'Settings', hrOnly: true },
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const session = useSessionStore()
  if (to.meta.public) return true
  if (!getToken()) return { name: 'sign-in', query: { next: to.fullPath } }
  if (!session.user) await session.hydrate()
  if (!session.user) return { name: 'sign-in' }
  if (to.meta.hrOnly && !session.isHr) return { name: 'dashboard' }
  return true
})

export default router
