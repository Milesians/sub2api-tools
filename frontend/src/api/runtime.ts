import { reactive } from 'vue'

export interface Feature {
  id: string
  name: string
  path: string
  visibility: string[]
}

export interface BootstrapResponse {
  session_token: string
  session_type: 'user' | 'admin'
  user: { id: string; username?: string; email?: string; role: string }
  app: { basePath: string; theme?: string; lang?: string }
  features: Feature[]
}

export const runtime = reactive<{
  boot: BootstrapResponse | null
  token: string
}>({
  boot: null,
  token: sessionStorage.getItem('sub2api_tools_session_token') || ''
})

export function apiURL(path: string): string {
  const base = joinPath(basePath(), '/api')
  const suffix = path.startsWith('/') ? path : `/${path}`
  return joinPath(base, suffix)
}

export function basePath(): string {
  return normalizeBasePath(runtime.boot?.app.basePath || detectBasePath())
}

export function authHeaders(): Record<string, string> {
  return runtime.token ? { Authorization: `Bearer ${runtime.token}` } : {}
}

export function iframeContext(): Record<string, string> {
  const params = new URLSearchParams(window.location.search)
  return {
    user_id: params.get('user_id') || '',
    ticket: params.get('ticket') || '',
    token: params.get('token') || '',
    legacy_token: params.get('legacy_token') || params.get('token') || '',
    theme: params.get('theme') || '',
    lang: params.get('lang') || '',
    ui_mode: params.get('ui_mode') || '',
    src_host: params.get('src_host') || '',
    src_url: params.get('src_url') || ''
  }
}

export async function bootstrap(): Promise<BootstrapResponse> {
  if (!hasIframeCredential() && runtime.token) {
    try {
      return await loadCurrentSession()
    } catch {
      sessionStorage.removeItem('sub2api_tools_session_token')
      runtime.token = ''
    }
  }
  const res = await fetch(apiURL('/auth/bootstrap'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    cache: 'no-store',
    body: JSON.stringify(iframeContext())
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body?.detail || `bootstrap failed: ${res.status}`)
  runtime.boot = body
  runtime.token = body.session_token
  sessionStorage.setItem('sub2api_tools_session_token', body.session_token)
  cleanTokenFromURL()
  return body
}

export async function loadCurrentSession(): Promise<BootstrapResponse> {
  const res = await fetch(apiURL('/auth/me'), {
    headers: authHeaders(),
    cache: 'no-store'
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body?.detail || `session restore failed: ${res.status}`)
  runtime.boot = body
  return body
}

function hasIframeCredential(): boolean {
  const params = new URLSearchParams(window.location.search)
  return Boolean(params.get('token') || params.get('ticket') || params.get('legacy_token'))
}

function cleanTokenFromURL() {
  const url = new URL(window.location.href)
  const keys = ['token', 'ticket', 'legacy_token']
  if (!keys.some((key) => url.searchParams.has(key))) return
  for (const key of keys) url.searchParams.delete(key)
  window.history.replaceState(null, '', `${url.pathname}${url.search}${url.hash}`)
}

function detectBasePath(): string {
  const current = normalizeBasePath(window.location.pathname)
  const segments = current.split('/').filter(Boolean)
  for (const featureSegment of ['lg', 'admin']) {
    const index = segments.indexOf(featureSegment)
    if (index >= 0) return normalizeBasePath(`/${segments.slice(0, index).join('/')}`)
  }
  return current
}

function joinPath(base: string, path: string): string {
  const cleanBase = normalizeBasePath(base)
  const cleanPath = `/${path.replace(/^\/+/, '')}`
  return cleanBase === '/' ? cleanPath : `${cleanBase}${cleanPath}`
}

function normalizeBasePath(value: string): string {
  const path = `/${value.replace(/^\/+/, '')}`.replace(/\/+$/g, '')
  return path || '/'
}
