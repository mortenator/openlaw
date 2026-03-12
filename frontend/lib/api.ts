import type {
  AgentConfig,
  Company,
  Contact,
  OutreachSuggestion,
  Signal,
  UserCron,
} from './types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function apiFetch<T>(token: string, path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options?.headers,
    },
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json()
}

export const api = {
  contacts: {
    list: (token: string, params?: { tier?: number; search?: string }) =>
      apiFetch<Contact[]>(token, '/contacts'),
    get: (token: string, id: string) => apiFetch<Contact>(token, `/contacts/${id}`),
    create: (token: string, data: Partial<Contact>) =>
      apiFetch<Contact>(token, '/contacts', { method: 'POST', body: JSON.stringify(data) }),
    update: (token: string, id: string, data: Partial<Contact>) =>
      apiFetch<Contact>(token, `/contacts/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  },
  companies: {
    list: (token: string, watchlist?: boolean) =>
      apiFetch<Company[]>(token, `/companies${watchlist ? '?watchlist=true' : ''}`),
    get: (token: string, id: string) => apiFetch<Company>(token, `/companies/${id}`),
    create: (token: string, data: Partial<Company>) =>
      apiFetch<Company>(token, '/companies', { method: 'POST', body: JSON.stringify(data) }),
    update: (token: string, id: string, data: Partial<Company>) =>
      apiFetch<Company>(token, `/companies/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  },
  suggestions: {
    list: (token: string, status?: string) =>
      apiFetch<OutreachSuggestion[]>(
        token,
        `/suggestions${status ? `?status=${status}` : ''}`
      ),
    update: (token: string, id: string, status: string) =>
      apiFetch<OutreachSuggestion>(token, `/suggestions/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ status }),
      }),
  },
  signals: {
    list: (token: string, params?: { company_id?: string; limit?: number }) =>
      apiFetch<Signal[]>(token, '/signals'),
  },
  agentConfigs: {
    list: (token: string) => apiFetch<AgentConfig[]>(token, '/agent/configs'),
    update: (token: string, fileName: string, content: string) =>
      apiFetch<AgentConfig>(token, `/agent/configs/${fileName}`, {
        method: 'PUT',
        body: JSON.stringify({ content }),
      }),
  },
  crons: {
    list: (token: string) => apiFetch<UserCron[]>(token, '/crons'),
    toggle: (token: string, id: string, isEnabled: boolean) =>
      apiFetch<UserCron>(token, `/crons/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ is_enabled: isEnabled }),
      }),
  },
  query: {
    send: (token: string, message: string) =>
      apiFetch<{ response: string }>(token, '/query', {
        method: 'POST',
        body: JSON.stringify({ message }),
      }),
  },
}
