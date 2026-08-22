import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { defineComponent, h } from 'vue'

import App from '../App.vue'

describe('App', () => {
  it('renders the router outlet', async () => {
    const stub = defineComponent({ setup: () => () => h('p', 'outlet ready') })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: stub }],
    })
    await router.push('/')
    await router.isReady()
    const wrapper = mount(App, { global: { plugins: [router] } })
    expect(wrapper.text()).toContain('outlet ready')
  })
})
