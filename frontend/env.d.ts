/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

export {}

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    hrOnly?: boolean
    title?: string
  }
}
