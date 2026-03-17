'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { Delivery } from '@/lib/types'

const STATUS_BADGE: Record<string, string> = {
  sent: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  pending: 'bg-gray-100 text-gray-700',
}

function formatDate(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleString()
}

function getSuggestionCount(payload: Record<string, unknown> | null): string {
  if (!payload) return '—'
  const ids = payload.suggestion_ids
  if (Array.isArray(ids)) return String(ids.length)
  return '—'
}

export default function DeliveriesPage() {
  const [deliveries, setDeliveries] = useState<Delivery[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      api.deliveries
        .list(session.access_token, session.user.id)
        .then((data) => {
          setDeliveries(data)
          setLoading(false)
        })
        .catch(() => setLoading(false))
    })
  }, [])

  function toggleRow(id: string) {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Deliveries</h1>

      {loading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400 animate-pulse">
          Loading...
        </div>
      ) : deliveries.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500 text-sm">
          No deliveries yet — digests will appear here after your first weekly send.
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Type</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Delivered At</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500"># Suggestions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {deliveries.map((d) => (
                <tr key={d.id} className="group">
                  <td colSpan={4} className="p-0">
                    <div
                      onClick={d.status === 'failed' ? () => toggleRow(d.id) : undefined}
                      className={`w-full text-left grid grid-cols-4 px-4 py-3 ${
                        d.status === 'failed' ? 'cursor-pointer hover:bg-gray-50' : ''
                      }`}
                    >
                      <span className="text-gray-700">{d.delivery_type}</span>
                      <span>
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                            STATUS_BADGE[d.status] ?? STATUS_BADGE.pending
                          }`}
                        >
                          {d.status}
                        </span>
                      </span>
                      <span className="text-gray-500">{formatDate(d.delivered_at)}</span>
                      <span className="text-gray-500">{getSuggestionCount(d.payload)}</span>
                    </div>
                    {expandedId === d.id && d.status === 'failed' && d.error_message && (
                      <div className="px-4 pb-3">
                        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                          {d.error_message}
                        </div>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
