'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { OutreachSuggestion, Signal, Contact } from '@/lib/types'
import { HealthBadge } from '@/components/HealthBadge'

const SIGNAL_COLORS: Record<string, string> = {
  new_gc: 'bg-purple-100 text-purple-700',
  deal_announced: 'bg-blue-100 text-blue-700',
  investment: 'bg-green-100 text-green-700',
  competitor_move: 'bg-red-100 text-red-700',
  general_news: 'bg-gray-100 text-gray-700',
}

export default function DashboardPage() {
  const [token, setToken] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<OutreachSuggestion[]>([])
  const [signals, setSignals] = useState<Signal[]>([])
  const [atRiskCount, setAtRiskCount] = useState(0)
  const [atRiskContacts, setAtRiskContacts] = useState<Contact[]>([])
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
        const needAttention = contacts.filter(
          (c) => (c.health_score ?? 100) < 40 && (c.tier === 1 || c.tier === 2)
        )
        setAtRiskCount(needAttention.length)
        const sorted = [...contacts]
          .sort((a, b) => (a.health_score ?? 0) - (b.health_score ?? 0))
          .slice(0, 5)
        setAtRiskContacts(sorted)
        setLoading(false)
      }).catch(() => setLoading(false))
    })
  }, [])

  function approve(id: string) {
    if (!token) return
    const previous = suggestions
    setSuggestions((prev) => prev.filter((s) => s.id !== id))
    api.suggestions.update(token, id, 'approved').catch(() => {
      setSuggestions(previous)
    })
  }

  function dismiss(id: string) {
    if (!token) return
    const previous = suggestions
    setSuggestions((prev) => prev.filter((s) => s.id !== id))
    api.suggestions.update(token, id, 'dismissed').catch(() => {
      setSuggestions(previous)
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

      {atRiskCount > 0 && (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-xl px-5 py-3 text-sm text-amber-800 font-medium">
          {atRiskCount} contact{atRiskCount !== 1 ? 's' : ''} need attention
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Pending Outreach */}
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Pending Outreach
          </h2>
          {suggestions.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-6 text-sm text-gray-500">
              No pending outreach — check back after the next weekly scan.
            </div>
          ) : (
            <div className="space-y-3">
              {suggestions.map((s) => (
                <div key={s.id} className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="font-medium text-gray-900 text-sm">
                    {s.contact?.name ?? 'Unknown'}
                    {s.contact?.role && (
                      <span className="font-normal text-gray-500"> — {s.contact.role}</span>
                    )}
                  </div>
                  {s.contact?.company && (
                    <div className="text-xs text-gray-500">{s.contact.company.name}</div>
                  )}
                  {s.trigger_summary && (
                    <div className="mt-2 px-3 py-2 bg-blue-50 border border-blue-100 rounded-lg text-xs text-blue-700">
                      <span className="font-semibold">Why now:</span> {s.trigger_summary}
                    </div>
                  )}
                  {s.draft_message && (
                    <div className="text-xs text-gray-500 mt-2 line-clamp-2">
                      {s.draft_message}
                    </div>
                  )}
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => approve(s.id)}
                      className="text-xs font-medium text-green-600 hover:text-green-800"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => dismiss(s.id)}
                      className="text-xs font-medium text-red-500 hover:text-red-700"
                    >
                      Dismiss
                    </button>
                  </div>
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
                    {sig.type.replace(/_/g, ' ')}
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
          {atRiskContacts.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-6 text-sm text-gray-500">
              All relationships healthy
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
              {atRiskContacts.map((c) => (
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
