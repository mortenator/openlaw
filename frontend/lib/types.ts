export interface Contact {
  id: string
  user_id: string
  company_id: string | null
  name: string
  role: string | null
  email: string | null
  tier: 1 | 2 | 3
  last_contacted_at: string | null
  health_score: number | null
  notes: string | null
  created_at: string
  company?: Company
}

export interface Company {
  id: string
  user_id: string
  name: string
  industry: string | null
  tags: string[]
  is_watchlist: boolean
  created_at: string
}

export interface Signal {
  id: string
  user_id: string
  company_id: string | null
  source: string | null
  headline: string
  url: string | null
  summary: string | null
  relevance_score: number | null
  created_at: string
}

export interface OutreachSuggestion {
  id: string
  user_id: string
  contact_id: string
  signal_id: string | null
  subject: string | null
  draft_message: string | null
  trigger_summary?: string | null
  status: 'pending' | 'dismissed' | 'sent'
  created_at: string
  contact?: Contact
}

export interface Delivery {
  id: string
  user_id: string
  delivery_type: string
  channel: string
  status: 'pending' | 'sent' | 'failed'
  payload: Record<string, unknown> | null
  error_message: string | null
  delivered_at: string | null
  created_at: string
}

export interface AgentConfig {
  id: string
  user_id: string
  file_name: 'SOUL.md' | 'USER.md' | 'AGENTS.md' | 'MEMORY.md' | 'HEARTBEAT.md'
  content: string
  updated_at: string
}

export interface UserCron {
  id: string
  user_id: string
  name: string
  cron_expression: string
  job_type: string
  is_active: boolean
  last_run_at: string | null
  created_at: string
}
