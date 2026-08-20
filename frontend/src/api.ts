import type { ChatRequest, ChatResponse, AnalyticsResponse } from './types'

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Server error ${res.status}`
    try {
      const body = await res.json()
      if (body?.detail) detail = body.detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export async function sendMessage(req: ChatRequest): Promise<ChatResponse> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  return handleResponse<ChatResponse>(res)
}

export async function fetchAnalytics(sessionId: string): Promise<AnalyticsResponse> {
  if (!sessionId) throw new Error('No session ID provided.')
  const res = await fetch(`${BASE_URL}/analytics/${encodeURIComponent(sessionId)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  return handleResponse<AnalyticsResponse>(res)
}
