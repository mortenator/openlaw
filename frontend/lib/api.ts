import type {
  AgentConfig,
  Company,
  Contact,
  Delivery,
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
    list: (token: string, params?: { tier?: number; search?: string }) => {
      const qs = new URLSearchParams()
      if (params?.tier) qs.set('tier', String(params.tier))
      if (params?.search) qs.set('search', params.search)
      const query = qs.toString()
      return apiFetch<Contact[]>(token, `/contacts${query ? `?${query}` : ''}`)
    },
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
    list: (token: string, params?: { company_id?: string; limit?: number }) => {
      const qs = new URLSearchParams()
      if (params?.company_id) qs.set('company_id', params.company_id)
      if (params?.limit) qs.set('limit', String(params.limit))
      const query = qs.toString()
      return apiFetch<Signal[]>(token, `/signals${query ? `?${query}` : ''}`)
    },
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
    create: (
      token: string,
      data: {
        name: string
        job_type: string
        cron_expression: string
        config: { keywords: string[] }
        is_active: boolean
      }
    ) =>
      apiFetch<UserCron>(token, '/crons', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    toggle: (token: string, id: string, isEnabled: boolean) =>
      apiFetch<UserCron>(token, `/crons/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ is_active: isEnabled }),
      }),
  },
  deliveries: {
    list: (token: string) => apiFetch<Delivery[]>(token, '/deliveries'),
  },
  query: {
    send: (token: string, message: string) =>
      apiFetch<{ response: string; tools_used: string[]; turns: number }>(token, '/query', {
        method: 'POST',
        body: JSON.stringify({ message }),
      }),
  },
  onboarding: {
    card: (
      token: string,
      data: { first_name: string; last_name: string; firm: string; role?: string; practice_area: string[] }
    ) =>
      apiFetch<{ step: number; next: string }>(token, '/onboarding/card', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    chat: (token: string, step: number, answer: unknown) =>
      apiFetch<{
        step: number
        agent_message: string
        input_type: 'chips' | 'free' | 'confirm'
        options?: string[]
      }>(token, '/onboarding/chat', {
        method: 'POST',
        body: JSON.stringify({ step, answer }),
      }),

    confirm: (token: string) =>
      apiFetch<{ success: boolean; redirect: string }>(token, '/onboarding/confirm', {
        method: 'POST',
      }),

    status: (token: string) =>
      apiFetch<{ step: number; complete: boolean; answers: Record<string, unknown> }>(
        token,
        '/onboarding/status'
      ),
  },
}
