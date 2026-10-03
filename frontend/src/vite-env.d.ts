/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Display name of the application. */
  readonly VITE_APP_NAME: string
  /**
   * Base URL for every API call, e.g. `/api` or `http://127.0.0.1:8000/api`.
   * Only `VITE_`-prefixed variables reach the browser bundle.
   */
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
