'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { Signal } from '@/lib/types'

const SIGNAL_COLORS: Record<string, string> = {
  new_gc: 'bg-purple-100 text-purple-700',
  deal_announced: 'bg-blue-100 text-blue-700',
  investment: 'bg-green-100 text-green-700',
  competitor_move: 'bg-red-100 text-red-700',
  general_news: 'bg-gray-100 text-gray-700',
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
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Market Signals</h1>

      {loading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400 animate-pulse">
          Loading...
        </div>
      ) : signals.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500 text-sm">
          No signals yet — run the market_brief job to populate signals
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Date</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Type</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Headline</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Summary</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {signals.map((sig) => (
                <tr key={sig.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                    {formatDate(sig.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                        SIGNAL_COLORS[sig.type] ?? SIGNAL_COLORS.general_news
                      }`}
                    >
                      {sig.type.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900 max-w-xs">
                    {sig.source_url ? (
                      <a
                        href={sig.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        {sig.headline}
                      </a>
                    ) : (
                      sig.headline
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500 max-w-sm">{sig.summary ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
