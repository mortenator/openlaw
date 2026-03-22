'use client'
export const dynamic = "force-dynamic"

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { Signal } from '@/lib/types'

const SIGNAL_COLORS: Record<string, { bg: string; text: string }> = {
  new_gc: { bg: '--purple-subtle', text: '--purple' },
  deal_announced: { bg: '--accent-subtle', text: '--accent-text' },
  investment: { bg: '--green-subtle', text: '--green' },
  competitor_move: { bg: '--red-subtle', text: '--red' },
  general_news: { bg: '--surface', text: '--text-secondary' },
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      api.signals.list(session.access_token).then((data) => {
        setSignals(data)
        setLoading(false)
      }).catch(() => setLoading(false))
    })
  }, [])

  return (
    <div>
      <h1
        style={{ color: 'var(--text-primary)' }}
        className="text-2xl font-semibold tracking-tight mb-6"
      >
        Market Signals
      </h1>

      {loading ? (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-tertiary)' }}
          className="rounded-xl p-8 text-center text-sm animate-pulse"
        >
          Loading...
        </div>
      ) : signals.length === 0 ? (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          className="rounded-xl p-8 text-center text-sm"
        >
          No signals yet — run the market_brief job to populate signals
        </div>
      ) : (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
          className="rounded-xl overflow-hidden"
        >
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Date</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Type</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Headline</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Summary</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((sig) => {
                const colors = SIGNAL_COLORS[sig.source ?? sig.type] ?? SIGNAL_COLORS.general_news
                return (
                  <tr
                    key={sig.id}
                    style={{ borderBottom: '1px solid var(--border-subtle)' }}
                    className="hover:opacity-80 transition-opacity"
                  >
                    <td style={{ color: 'var(--text-tertiary)' }} className="px-4 py-3 whitespace-nowrap">
                      {formatDate(sig.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        style={{ background: `var(${colors.bg})`, color: `var(${colors.text})` }}
                        className="inline-block px-2 py-0.5 rounded-full text-xs font-medium"
                      >
                        {((sig.source ?? sig.type ?? 'general_news').replace(/_/g, ' '))}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-primary)' }} className="px-4 py-3 font-medium max-w-xs">
                      {sig.url ?? sig.source_url ? (
                        <a
                          href={sig.url ?? sig.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: 'var(--accent-text)' }}
                          className="hover:underline"
                        >
                          {sig.headline}
                        </a>
                      ) : (
                        sig.headline
                      )}
                    </td>
                    <td style={{ color: 'var(--text-secondary)' }} className="px-4 py-3 max-w-sm">{sig.summary ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
