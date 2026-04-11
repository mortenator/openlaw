'use client'
export const dynamic = "force-dynamic"

import { useEffect, useRef, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { OutreachSuggestion, Signal, Contact } from '@/lib/types'
import { HealthBadge } from '@/components/HealthBadge'
import { Users, Send, Zap, Activity, X, ExternalLink, ArrowUpRight, Loader2, CheckCircle2 } from 'lucide-react'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const SIGNAL_STYLES: Record<string, { bg: string; text: string }> = {
  new_gc: { bg: '--purple-subtle', text: '--purple' },
  deal_announced: { bg: '--accent-subtle', text: '--accent-text' },
  investment: { bg: '--green-subtle', text: '--green' },
  competitor_move: { bg: '--red-subtle', text: '--red' },
  general_news: { bg: '--surface', text: '--text-secondary' },
}

type EnrichedSignalSource = {
  title?: string
  url?: string
}

type EnrichedSignalData = {
  full_summary?: string
  article_body?: string
  key_points?: string[]
  why_it_matters?: string
  sources?: EnrichedSignalSource[]
  raw_data?: EnrichedSignalData
}

export default function DashboardPage() {
  const [token, setToken] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<OutreachSuggestion[]>([])
  const [approvedSuggestions, setApprovedSuggestions] = useState<OutreachSuggestion[]>([])
  const [pendingSuggestionIds, setPendingSuggestionIds] = useState<Set<string>>(new Set())
  const [approvalError, setApprovalError] = useState<string | null>(null)
  const [signals, setSignals] = useState<Signal[]>([])
  const [contacts, setContacts] = useState<Contact[]>([])
  const [atRiskContacts, setAtRiskContacts] = useState<Contact[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null)
  const [enrichedData, setEnrichedData] = useState<EnrichedSignalData | null>(null)
  const [enriching, setEnriching] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)
      Promise.all([
        api.suggestions.list(t, 'pending'),
        api.suggestions.list(t, 'approved'),
        api.signals.list(t),
        api.contacts.list(t),
      ]).then(([s, approved, sig, allContacts]) => {
        setSuggestions(s)
        setApprovedSuggestions(approved)
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

  async function openSignal(sig: Signal) {
    setSelectedSignal(sig)
    setEnrichedData(null)
    if (!token) return
    setEnriching(true)
    try {
      const res = await fetch(`${BASE_URL}/signals/${sig.id}/enrich`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      })
      if (res.ok) {
        const data = await res.json()
        setEnrichedData(data.raw_data || null)
      }
    } catch {
      // fallback — show what we have
    } finally {
      setEnriching(false)
    }
  }

  function closeSignal() {
    setSelectedSignal(null)
    setEnrichedData(null)
  }

  function isSafeExternalUrl(url: string | null | undefined) {
    return typeof url === 'string' && url.startsWith('https://')
  }

  function approve(id: string) {
    if (!token || pendingSuggestionIds.has(id)) return
    setApprovalError(null)
    const previous = suggestions
    const target = suggestions.find((s) => s.id === id)
    setPendingSuggestionIds((prev) => new Set(prev).add(id))
    setSuggestions((prev) => prev.filter((s) => s.id !== id))
    api.suggestions.update(token, id, 'approved').then((updated) => {
      setApprovedSuggestions((prev) => [...prev, { ...target!, ...updated }])
    }).catch((error: unknown) => {
      setSuggestions(previous)
      const message = error instanceof Error ? error.message : 'Could not send to review'
      setApprovalError(message)
    }).finally(() => {
      setPendingSuggestionIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    })
  }

  function dismiss(id: string) {
    if (!token || pendingSuggestionIds.has(id)) return
    const previous = suggestions
    setPendingSuggestionIds((prev) => new Set(prev).add(id))
    setSuggestions((prev) => prev.filter((s) => s.id !== id))
    api.suggestions.update(token, id, 'dismissed').catch(() => {
      setSuggestions(previous)
    }).finally(() => {
      setPendingSuggestionIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
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
              {approvalError && (
                <div
                  style={{ background: 'var(--red-subtle)', color: 'var(--red)', border: '1px solid var(--border)' }}
                  className="rounded-xl p-3 text-xs"
                >
                  {approvalError}
                </div>
              )}
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
                      disabled={pendingSuggestionIds.has(s.id)}
                      style={{ color: 'var(--green)' }}
                      className="text-xs font-medium hover:opacity-80 disabled:opacity-50"
                    >
                      {pendingSuggestionIds.has(s.id) ? 'Sending…' : 'Send to review'}
                    </button>
                    <button
                      onClick={() => dismiss(s.id)}
                      disabled={pendingSuggestionIds.has(s.id)}
                      style={{ color: 'var(--red)' }}
                      className="text-xs font-medium hover:opacity-80 disabled:opacity-50"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Approved — review requested */}
          {approvedSuggestions.length > 0 && (
            <>
              <div
                style={{ borderBottom: '1px solid var(--border)', color: 'var(--text-tertiary)' }}
                className="text-xs font-medium uppercase tracking-wider pb-3 mb-4 mt-6"
              >
                Review Requested
              </div>
              <div className="space-y-3">
                {approvedSuggestions.map((s) => (
                  <div
                    key={s.id}
                    style={{ background: 'var(--bg-elevated)', border: '1px solid var(--green-subtle, var(--border))' }}
                    className="rounded-xl p-4"
                  >
                    <div className="flex items-center gap-2">
                      <CheckCircle2 size={14} style={{ color: 'var(--green)' }} />
                      <div style={{ color: 'var(--text-primary)' }} className="font-medium text-sm">
                        {s.contact?.name ?? 'Unknown'}
                      </div>
                    </div>
                    {s.subject && (
                      <div style={{ color: 'var(--text-tertiary)' }} className="text-xs mt-1">{s.subject}</div>
                    )}
                    {isSafeExternalUrl(s.paperclip_issue_url) ? (
                      <a
                        href={s.paperclip_issue_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: 'var(--accent-text)' }}
                        className="mt-2 inline-flex items-center gap-1 text-xs font-medium hover:opacity-80"
                      >
                        {s.paperclip_issue_identifier ? `View ${s.paperclip_issue_identifier} in Paperclip` : 'View in Paperclip'}
                        <ExternalLink size={12} />
                      </a>
                    ) : (s.paperclip_issue_identifier || s.paperclip_issue_id) ? (
                      <div style={{ color: 'var(--text-tertiary)' }} className="text-xs mt-2">
                        Issue {s.paperclip_issue_identifier ?? s.paperclip_issue_id}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </>

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
                const style = SIGNAL_STYLES[sig.source || "general_news"] ?? SIGNAL_STYLES.general_news
                const isSelected = selectedSignal?.id === sig.id
                return (
                  <div
                    key={sig.id}
                    onClick={() => isSelected ? closeSignal() : openSignal(sig)}
                    style={{
                      background: isSelected ? 'var(--surface)' : 'var(--bg-elevated)',
                      border: `1px solid ${isSelected ? 'var(--accent)' : 'var(--border)'}`,
                      cursor: 'pointer',
                    }}
                    className="rounded-xl p-4 transition-all hover:opacity-90"
                  >
                    <span
                      style={{ background: `var(${style.bg})`, color: `var(${style.text})` }}
                      className="inline-block px-2 py-0.5 rounded-full text-xs font-medium mb-2"
                    >
                      {(sig.source || "general_news").replace(/_/g, ' ')}
                    </span>
                    <div style={{ color: 'var(--text-primary)' }} className="text-sm font-medium">
                      {sig.headline}
                    </div>
                    {sig.summary && (
                      <div style={{ color: 'var(--text-tertiary)' }} className="text-xs mt-1 line-clamp-2">
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

      {/* Signal detail panel */}
      {selectedSignal && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-30"
            onClick={closeSignal}
          />
          {/* Panel */}
          <div
            ref={panelRef}
            style={{
              background: 'var(--bg-elevated)',
              borderLeft: '1px solid var(--border)',
              width: '400px',
            }}
            className="fixed top-0 right-0 h-full z-40 flex flex-col shadow-2xl"
          >
            {/* Panel header */}
            <div
              style={{ borderBottom: '1px solid var(--border)' }}
              className="flex items-center justify-between px-6 py-4"
            >
              <div>
                <span
                  style={{
                    background: `var(${(SIGNAL_STYLES[selectedSignal.source || 'general_news'] ?? SIGNAL_STYLES.general_news).bg})`,
                    color: `var(${(SIGNAL_STYLES[selectedSignal.source || 'general_news'] ?? SIGNAL_STYLES.general_news).text})`,
                  }}
                  className="inline-block px-2 py-0.5 rounded-full text-xs font-medium"
                >
                  {(selectedSignal.source || 'general_news').replace(/_/g, ' ')}
                </span>
              </div>
              <button
                onClick={closeSignal}
                style={{ color: 'var(--text-tertiary)' }}
                className="hover:opacity-70 transition-opacity cursor-pointer p-1 rounded"
              >
                <X size={18} />
              </button>
            </div>

            {/* Panel body */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
              {/* Headline */}
              <h2
                style={{ color: 'var(--text-primary)' }}
                className="text-base font-semibold leading-snug"
              >
                {selectedSignal.headline}
              </h2>

              {enriching ? (
                <div className="flex items-center gap-3 py-8 justify-center">
                  <Loader2 size={18} style={{ color: 'var(--accent)' }} className="animate-spin" />
                  <span style={{ color: 'var(--text-tertiary)' }} className="text-sm">Enriching with Claude...</span>
                </div>
              ) : enrichedData ? (
                <>
                  {/* Full summary */}
                  {enrichedData.full_summary && (
                    <div>
                      <div style={{ color: 'var(--text-tertiary)' }} className="text-xs font-medium uppercase tracking-wider mb-2">Summary</div>
                      <p style={{ color: 'var(--text-secondary)' }} className="text-sm leading-relaxed">{enrichedData.full_summary}</p>
                    </div>
                  )}

                  {/* Article body */}
                  {enrichedData.article_body && (
                    <div>
                      <div style={{ color: 'var(--text-tertiary)' }} className="text-xs font-medium uppercase tracking-wider mb-3">Full Story</div>
                      <div style={{ color: 'var(--text-secondary)', borderLeft: '2px solid var(--border)' }} className="pl-4 space-y-3">
                        {enrichedData.article_body.split('\n\n').filter(Boolean).map((para: string, i: number) => (
                          <p key={i} className="text-sm leading-relaxed">{para}</p>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Key points */}
                  {enrichedData.key_points?.length > 0 && (
                    <div>
                      <div style={{ color: 'var(--text-tertiary)' }} className="text-xs font-medium uppercase tracking-wider mb-2">Key Points</div>
                      <ul className="space-y-2">
                        {enrichedData.key_points.map((pt: string, i: number) => (
                          <li key={i} className="flex gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                            <span style={{ color: 'var(--accent)' }} className="mt-0.5 flex-shrink-0">•</span>
                            <span>{pt}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Why it matters */}
                  {enrichedData.why_it_matters && (
                    <div style={{ background: 'var(--accent-subtle)', borderLeft: '3px solid var(--accent)' }} className="px-4 py-3 rounded-r-lg">
                      <div style={{ color: 'var(--accent-text)' }} className="text-xs font-semibold uppercase tracking-wider mb-1">Why It Matters</div>
                      <p style={{ color: 'var(--accent-text)' }} className="text-sm leading-relaxed opacity-90">{enrichedData.why_it_matters}</p>
                    </div>
                  )}

                  {/* Sources */}
                  {enrichedData.sources?.length > 0 && (
                    <div>
                      <div style={{ color: 'var(--text-tertiary)' }} className="text-xs font-medium uppercase tracking-wider mb-2">Sources</div>
                      <div className="space-y-2">
                        {enrichedData.sources.map((src, i: number) => (
                          isSafeExternalUrl(src.url) ? (
                            <a
                              key={i}
                              href={src.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--accent-text)' }}
                              className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm hover:opacity-80 transition-opacity"
                            >
                              <ExternalLink size={13} className="flex-shrink-0" />
                              <span className="truncate flex-1">{src.title || src.url.replace(/^https?:\/\//, '').split('/')[0]}</span>
                              <ArrowUpRight size={13} className="flex-shrink-0" />
                            </a>
                          ) : (
                            <div key={i} style={{ color: 'var(--text-secondary)' }} className="text-sm px-3 py-2">{src.title}</div>
                          )
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                /* Fallback: just show the raw summary */
                selectedSignal.summary && (
                  <div>
                    <div style={{ color: 'var(--text-tertiary)' }} className="text-xs font-medium uppercase tracking-wider mb-2">Summary</div>
                    <p style={{ color: 'var(--text-secondary)' }} className="text-sm leading-relaxed">{selectedSignal.summary}</p>
                  </div>
                )
              )}

              {/* Metadata */}
              <div style={{ borderTop: '1px solid var(--border)' }} className="pt-4 space-y-2">
                {selectedSignal.created_at && (
                  <div className="flex justify-between text-xs">
                    <span style={{ color: 'var(--text-tertiary)' }}>Captured</span>
                    <span style={{ color: 'var(--text-secondary)' }}>{new Date(selectedSignal.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Panel footer */}
            <div
              style={{ borderTop: '1px solid var(--border)' }}
              className="px-6 py-4"
            >
              {isSafeExternalUrl(selectedSignal.url) ? (
                <a
                  href={selectedSignal.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ background: 'var(--accent)' }}
                  className="w-full flex items-center justify-center gap-2 py-2.5 text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity"
                >
                  Read Full Article
                  <ExternalLink size={14} />
                </a>
              ) : (
                <div
                  style={{ color: 'var(--text-tertiary)' }}
                  className="text-xs text-center"
                >
                  No source URL available
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
