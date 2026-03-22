'use client'
export const dynamic = "force-dynamic"

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { OutreachSuggestion, Signal, Contact } from '@/lib/types'
import { HealthBadge } from '@/components/HealthBadge'
import { Users, Send, Zap, Activity } from 'lucide-react'

const SIGNAL_STYLES: Record<string, { bg: string; text: string }> = {
  new_gc: { bg: '--purple-subtle', text: '--purple' },
  deal_announced: { bg: '--accent-subtle', text: '--accent-text' },
  investment: { bg: '--green-subtle', text: '--green' },
  competitor_move: { bg: '--red-subtle', text: '--red' },
  general_news: { bg: '--surface', text: '--text-secondary' },
}

export default function DashboardPage() {
  const [token, setToken] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<OutreachSuggestion[]>([])
  const [signals, setSignals] = useState<Signal[]>([])
  const [contacts, setContacts] = useState<Contact[]>([])
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
      ]).then(([s, sig, allContacts]) => {
        setSuggestions(s)
        setSignals(sig.slice(0, 5))
        setContacts(allContacts)
        const atRisk = allContacts.filter(
          (c) => (c.health_score ?? 100) < 40 && (c.tier === 1 || c.tier === 2)
        )
        const sorted = atRisk
          .sort((a, b) => (a.health_score ?? 100) - (b.health_score ?? 100))
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

  const avgHealth = contacts.length > 0
    ? Math.round(contacts.reduce((sum, c) => sum + (c.health_score ?? 0), 0) / contacts.length)
    : 0

  if (loading) {
    return (
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
            className="rounded-xl p-5 h-24 animate-pulse"
          />
        ))}
      </div>
    )
  }

  const stats = [
    { icon: Users, label: 'Contacts', value: contacts.length.toString() },
    { icon: Send, label: 'Pending Outreach', value: suggestions.length.toString() },
    { icon: Zap, label: 'Market Signals', value: signals.length.toString() },
    { icon: Activity, label: 'Avg Health', value: `${avgHealth}%` },
  ]

  return (
    <div>
      <h1
        style={{ color: 'var(--text-primary)' }}
        className="text-2xl font-semibold tracking-tight mb-6"
      >
        Today&apos;s Briefing
      </h1>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {stats.map(({ icon: Icon, label, value }) => (
          <div
            key={label}
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
            className="rounded-xl p-5 flex items-start gap-4"
          >
            <div
              style={{ background: 'var(--accent-subtle)' }}
              className="p-2.5 rounded-lg"
            >
              <Icon size={18} style={{ color: 'var(--accent-text)' }} />
            </div>
            <div>
              <div
                style={{ color: 'var(--text-tertiary)' }}
                className="text-xs font-medium uppercase tracking-wider mb-1"
              >
                {label}
              </div>
              <div
                style={{ color: 'var(--text-primary)' }}
                className="text-2xl font-semibold"
              >
                {value}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Three columns */}
      <div className="grid grid-cols-3 gap-6">
        {/* Pending Outreach */}
        <div>
          <div
            style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-tertiary)' }}
            className="text-xs font-medium uppercase tracking-wider pb-3 mb-4"
          >
            Pending Outreach
          </div>
          {suggestions.length === 0 ? (
            <div
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
              className="rounded-xl p-6 text-sm"
            >
              No pending outreach — check back after the next weekly scan.
            </div>
          ) : (
            <div className="space-y-3">
              {suggestions.map((s) => (
                <div
                  key={s.id}
                  style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                  className="rounded-xl p-4"
                >
                  <div style={{ color: 'var(--text-primary)' }} className="font-medium text-sm">
                    {s.contact?.name ?? 'Unknown'}
                    {s.contact?.role && (
                      <span style={{ color: 'var(--text-secondary)' }} className="font-normal"> — {s.contact.role}</span>
                    )}
                  </div>
                  {s.contact?.company && (
                    <div style={{ color: 'var(--text-tertiary)' }} className="text-xs">{s.contact.company.name}</div>
                  )}
                  {s.trigger_summary && (
                    <div
                      style={{ background: 'var(--accent-subtle)', color: 'var(--accent-text)' }}
                      className="mt-2 px-3 py-2 rounded-lg text-xs"
                    >
                      <span className="font-semibold">Why now:</span> {s.trigger_summary}
                    </div>
                  )}
                  {s.draft_message && (
                    <div style={{ color: 'var(--text-tertiary)' }} className="text-xs mt-2 line-clamp-2">
                      {s.draft_message}
                    </div>
                  )}
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => approve(s.id)}
                      style={{ color: 'var(--green)' }}
                      className="text-xs font-medium hover:opacity-80"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => dismiss(s.id)}
                      style={{ color: 'var(--red)' }}
                      className="text-xs font-medium hover:opacity-80"
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
          <div
            style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-tertiary)' }}
            className="text-xs font-medium uppercase tracking-wider pb-3 mb-4"
          >
            Market Signals
          </div>
          {signals.length === 0 ? (
            <div
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
              className="rounded-xl p-6 text-sm"
            >
              No signals yet — agent will populate these on first run
            </div>
          ) : (
            <div className="space-y-3">
              {signals.map((sig) => {
                const style = SIGNAL_STYLES[sig.source ?? sig.type] ?? SIGNAL_STYLES.general_news
                return (
                  <div
                    key={sig.id}
                    style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                    className="rounded-xl p-4"
                  >
                    <span
                      style={{ background: `var(${style.bg})`, color: `var(${style.text})` }}
                      className="inline-block px-2 py-0.5 rounded-full text-xs font-medium mb-2"
                    >
                      {((sig.source ?? sig.type ?? 'general_news').replace(/_/g, ' '))}
                    </span>
                    {sig.url ?? sig.source_url ? (
                      <a
                        href={sig.url ?? sig.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: 'var(--accent-text)' }}
                        className="block text-sm font-medium hover:underline"
                      >
                        {sig.headline}
                      </a>
                    ) : (
                      <div style={{ color: 'var(--text-primary)' }} className="text-sm font-medium">
                        {sig.headline}
                      </div>
                    )}
                    {sig.summary && (
                      <div style={{ color: 'var(--text-tertiary)' }} className="text-xs mt-1">
                        {sig.summary}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* At-Risk Relationships */}
        <div>
          <div
            style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-tertiary)' }}
            className="text-xs font-medium uppercase tracking-wider pb-3 mb-4"
          >
            At-Risk Relationships
          </div>
          {atRiskContacts.length === 0 ? (
            <div
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
              className="rounded-xl p-6 text-sm"
            >
              All relationships healthy
            </div>
          ) : (
            <div
              style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
              className="rounded-xl divide-y"
            >
              {atRiskContacts.map((c) => {
                const score = c.health_score ?? 0
                const rowBg = score < 20 ? 'var(--red-subtle)' : score < 40 ? 'var(--amber-subtle)' : 'transparent'
                return (
                  <div
                    key={c.id}
                    style={{ background: rowBg, borderColor: 'var(--border)' }}
                    className="flex items-center justify-between px-4 py-3"
                  >
                    <div>
                      <div style={{ color: 'var(--text-primary)' }} className="text-sm font-medium">
                        {c.name}
                      </div>
                      <div style={{ color: 'var(--text-tertiary)' }} className="text-xs">
                        {c.role ?? ''}
                      </div>
                    </div>
                    <HealthBadge score={c.health_score} />
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
