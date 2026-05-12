/**
 * Typed API client for AimHigher backend.
 * All requests go through apiFetch which handles auth, errors, and retries.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, text)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// ── Types ────────────────────────────────────────────────────────────────────

export type Stage    = 'discovered' | 'contacted' | 'qualified' | 'onboarding' | 'converted' | 'disqualified' | 'dead'
export type Priority = 'hot' | 'warm' | 'cold'
export type Chain    = 'ethereum' | 'bnb' | 'solana' | 'base'
export type Channel  = 'twitter' | 'telegram' | 'discord'

export interface Lead {
  id: string
  project_name: string
  token_symbol: string | null
  chain: Chain
  contract_address: string | null
  website: string | null
  contact_links: Record<string, string>
  market_cap_usd: number | null
  score: number
  priority: Priority
  stage: Stage
  pain_signals: string[]
  activity_metrics: Record<string, unknown>
  qualification_score: number | null
  qualification_data: Record<string, unknown>
  onboarding_step: number
  source_platform: string | null
  first_seen_at: string
  last_activity_at: string
  converted_at: string | null
  created_at: string
  updated_at: string
}

export interface LeadList { total: number; page: number; page_size: number; items: Lead[] }

export interface Message {
  id: string
  conversation_id: string
  direction: 'inbound' | 'outbound'
  content: string
  ai_generated: boolean
  model_used: string | null
  created_at: string
}

export interface Conversation {
  id: string
  lead_id: string
  channel: Channel
  external_thread_id: string | null
  is_active: boolean
  created_at: string
  last_message_at: string | null
  messages: Message[]
}

export interface DashboardStats {
  total_leads: number
  by_stage: Record<string, number>
  by_priority: Record<string, number>
  by_chain: Record<string, number>
  conversion_rate: number
  avg_score: number
  messages_sent_7d: number
  replies_received_7d: number
  new_leads_7d: number
  converted_7d: number
}

export interface AgentStatus {
  hunter: boolean
  outreach: boolean
  qualification: boolean
  onboarding: boolean
  conversion: boolean
}

export interface OnboardingProgress {
  lead_id: string
  project_name: string
  stage: Stage
  current_step: number
  total_steps: number
  pct_complete: number
  steps: { step: number; name: string; goal: string; status: 'completed' | 'current' | 'pending' }[]
}

// ── Lead API ─────────────────────────────────────────────────────────────────

export const leadsApi = {
  list: (params?: Record<string, string | number>) => {
    const qs = params ? '?' + new URLSearchParams(params as Record<string, string>).toString() : ''
    return apiFetch<LeadList>(`/api/v1/leads${qs}`)
  },
  get: (id: string) => apiFetch<Lead>(`/api/v1/leads/${id}`),
  update: (id: string, data: Partial<Lead>) =>
    apiFetch<Lead>(`/api/v1/leads/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  transition: (id: string, stage: Stage, reason?: string) =>
    apiFetch<Lead>(`/api/v1/leads/${id}/transition`, {
      method: 'POST', body: JSON.stringify({ stage, reason }),
    }),
  conversations: (id: string) => apiFetch<Conversation[]>(`/api/v1/leads/${id}/conversations`),
  events: (id: string) => apiFetch<unknown[]>(`/api/v1/leads/${id}/events`),
  delete: (id: string) => apiFetch<void>(`/api/v1/leads/${id}`, { method: 'DELETE' }),
}

// ── Outreach API ──────────────────────────────────────────────────────────────

export const outreachApi = {
  send: (lead_id: string, channel: Channel, custom_note?: string) =>
    apiFetch('/api/v1/outreach/send', {
      method: 'POST', body: JSON.stringify({ lead_id, channel, custom_note }),
    }),
  ingestReply: (data: unknown) =>
    apiFetch('/api/v1/outreach/reply', { method: 'POST', body: JSON.stringify(data) }),
}

// ── Analytics API ─────────────────────────────────────────────────────────────

export const analyticsApi = {
  dashboard: () => apiFetch<DashboardStats>('/api/v1/analytics/dashboard'),
}

// ── Agents API ────────────────────────────────────────────────────────────────

export const agentsApi = {
  status: () => apiFetch<AgentStatus>('/api/v1/agents/status'),
  toggle: (agent: keyof AgentStatus, enabled: boolean) =>
    apiFetch<AgentStatus>('/api/v1/agents/toggle', {
      method: 'POST', body: JSON.stringify({ agent, enabled }),
    }),
}

// ── Hunter API ────────────────────────────────────────────────────────────────

export const hunterApi = {
  run: () => apiFetch('/api/v1/hunter/run', { method: 'POST' }),
  queueDepths: () => apiFetch<Record<string, number>>('/api/v1/hunter/queue-depth'),
}

// ── Onboarding API ────────────────────────────────────────────────────────────

export const onboardingApi = {
  chat: (lead_id: string, user_message: string) =>
    apiFetch('/api/v1/onboarding/chat', {
      method: 'POST', body: JSON.stringify({ lead_id, user_message }),
    }),
  progress: (id: string) => apiFetch<OnboardingProgress>(`/api/v1/onboarding/${id}/progress`),
  advance: (id: string) =>
    apiFetch(`/api/v1/onboarding/${id}/advance`, { method: 'POST' }),
}

// ── Qualification API ─────────────────────────────────────────────────────────

export const qualificationApi = {
  qualifyNow: (id: string) =>
    apiFetch(`/api/v1/qualification/${id}/qualify-now`, { method: 'POST' }),
  result: (id: string) => apiFetch(`/api/v1/qualification/${id}/result`),
  handleObjection: (id: string, objection: string, conversation_history: unknown[]) =>
    apiFetch(`/api/v1/qualification/${id}/handle-objection`, {
      method: 'POST', body: JSON.stringify({ objection, conversation_history }),
    }),
}

// ── Suggestions API ───────────────────────────────────────────────────────────

export const suggestionsApi = {
  get: (lead_id: string, conversation_id: string, last_inbound: string) =>
    apiFetch<{ suggestions: string[] }>('/api/v1/suggestions', {
      method: 'POST', body: JSON.stringify({ lead_id, conversation_id, last_inbound }),
    }),
}

// ── Knowledge API ─────────────────────────────────────────────────────────────

export const knowledgeApi = {
  list: () => apiFetch('/api/v1/knowledge'),
  search: (query: string, top_k = 5) =>
    apiFetch('/api/v1/knowledge/search', {
      method: 'POST', body: JSON.stringify({ query, top_k }),
    }),
  upload: (data: { title: string; content: string; source_url?: string }) =>
    apiFetch('/api/v1/knowledge', { method: 'POST', body: JSON.stringify(data) }),
}

// ── SWR fetcher (default) ─────────────────────────────────────────────────────

export const fetcher = <T>(url: string) => apiFetch<T>(url)
