'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { OutreachSuggestion, Signal, Contact } from '@/lib/types'

const SIGNAL_COLORS: Record<string, string> = {
  new_gc: 'bg-purple-100 text-purple-700',
  deal_announced: 'bg-blue-100 text-blue-700',
  investment: 'bg-green-100 text-green-700',
  competitor_move: 'bg-red-100 text-red-700',
  general_news: 'bg-gray-100 text-gray-700',
}

function HealthBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-400 text-sm">—</span>
  const cls =
    score < 40
      ? 'bg-red-100 text-red-700'
      : score <= 70
      ? 'bg-yellow-100 text-yellow-700'
      : 'bg-green-100 text-green-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {score}
    </span>
  )
}

export default function DashboardPage() {
  const [token, setToken] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<OutreachSuggestion[]>([])
  const [signals, setSignals] = useState<Signal[]>([])
  const [atRisk, setAtRisk] = useState<Contact[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)
      Promise.all([
        api.suggestions.list(t, 'pending'),
        api.signals.list(t),
        api.contacts.list(t),
      ]).then(([s, sig, contacts]) => {
        setSuggestions(s)
        setSignals(sig.slice(0, 5))
        const sorted = [...contacts]
          .sort((a, b) => (a.health_score ?? 0) - (b.health_score ?? 0))
          .slice(0, 5)
        setAtRisk(sorted)
        setLoading(false)
      }).catch(() => setLoading(false))
    })
  }, [])

  function dismiss(id: string) {
    if (!token) return
    api.suggestions.update(token, id, 'dismissed').then(() => {
      setSuggestions((prev) => prev.filter((s) => s.id !== id))
    })
  }

  if (loading) {
    return (
      <div className="grid grid-cols-3 gap-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse h-64" />
        ))}
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Today&apos;s Briefing</h1>
      <div className="grid grid-cols-3 gap-6">
        {/* Pending Outreach */}
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Pending Outreach
          </h2>
          {suggestions.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-6 text-sm text-gray-500">
              No pending outreach — you&apos;re all caught up
            </div>
          ) : (
            <div className="space-y-3">
              {suggestions.map((s) => (
                <div key={s.id} className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="font-medium text-gray-900 text-sm">
                    {s.contact?.name ?? 'Unknown'}
                  </div>
                  {s.trigger_summary && (
                    <div className="text-xs italic text-gray-400 mt-0.5">{s.trigger_summary}</div>
                  )}
                  {s.contact?.company && (
                    <div className="text-xs text-gray-500 mb-1">{(s.contact as any).company?.name}</div>
                  )}
                  {s.subject && (
                    <div className="text-xs font-medium text-gray-700 mt-1">{s.subject}</div>
                  )}
                  {s.draft_message && (
                    <div className="text-xs text-gray-500 mt-1">
                      {s.draft_message.slice(0, 120)}
                      {s.draft_message.length > 120 ? '...' : ''}
                    </div>
                  )}
                  <button
                    onClick={() => dismiss(s.id)}
                    className="mt-2 text-xs text-red-500 hover:text-red-700"
                  >
                    Dismiss
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Market Signals */}
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Market Signals
          </h2>
          {signals.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-6 text-sm text-gray-500">
              No signals yet — agent will populate these on first run
            </div>
          ) : (
            <div className="space-y-3">
              {signals.map((sig) => (
                <div key={sig.id} className="bg-white rounded-xl border border-gray-200 p-4">
                  <span
                    className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium mb-2 ${
                      SIGNAL_COLORS[sig.type] ?? SIGNAL_COLORS.general_news
                    }`}
                  >
                    {sig.type.replace('_', ' ')}
                  </span>
                  {sig.source_url ? (
                    <a
                      href={sig.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block text-sm font-medium text-blue-600 hover:underline"
                    >
                      {sig.headline}
                    </a>
                  ) : (
                    <div className="text-sm font-medium text-gray-900">{sig.headline}</div>
                  )}
                  {sig.summary && (
                    <div className="text-xs text-gray-500 mt-1">{sig.summary}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* At-Risk Relationships */}
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            At-Risk Relationships
          </h2>
          {atRisk.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-6 text-sm text-gray-500">
              All relationships healthy
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
              {atRisk.map((c) => (
                <div key={c.id} className="flex items-center justify-between px-4 py-3">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{c.name}</div>
                    <div className="text-xs text-gray-500">{c.role ?? ''}</div>
                  </div>
                  <HealthBadge score={c.health_score} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
