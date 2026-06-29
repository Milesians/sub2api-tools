import { apiURL, authHeaders } from './runtime'
import type { EndpointResult, EntryPoint, ProbeConfig } from '../types'

export interface EntrypointSnapshot {
  source: string
  public_path: string
  entrypoints: EntryPoint[]
  entrypoint_count: number
  probe: ProbeConfig
}

export async function getEntrypoints(): Promise<EntrypointSnapshot> {
  const res = await fetch(apiURL('/lg/entrypoints'), {
    headers: authHeaders(),
    cache: 'no-store'
  })
  return responseJSON(res, 'entrypoints failed')
}

export async function submitLGReport(payload: unknown): Promise<{ report_id: string; report: any }> {
  const res = await fetch(apiURL('/lg/reports'), {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    cache: 'no-store',
    body: JSON.stringify(payload)
  })
  return responseJSON(res, 'report submit failed')
}

export function resultLabel(result: EndpointResult): string {
  const success = `${Math.round(result.browser.success_rate * 100)}%`
  const p95 = result.browser.p95_duration_ms == null ? '-' : `${result.browser.p95_duration_ms}ms`
  return `${success} / P95 ${p95}`
}

async function responseJSON<T>(res: Response, fallback: string): Promise<T> {
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body?.detail || `${fallback}: ${res.status}`)
  return body as T
}
