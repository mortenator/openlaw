'use client'
export const dynamic = "force-dynamic"

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { Delivery } from '@/lib/types'

const STATUS_BADGE: Record<string, { bg: string; text: string }> = {
  sent: { bg: '--green-subtle', text: '--green' },
  failed: { bg: '--red-subtle', text: '--red' },
  pending: { bg: '--surface', text: '--text-secondary' },
}

function formatDate(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleString()
}

function PayloadModal({
  delivery,
  onClose,
}: {
  delivery: Delivery
  onClose: () => void
}) {
  const colors = STATUS_BADGE[delivery.status] ?? STATUS_BADGE.pending
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
        className="rounded-xl shadow-lg w-full max-w-lg max-h-[80vh] flex flex-col"
      >
        <div
          style={{ borderBottom: '1px solid var(--border)' }}
          className="flex items-center justify-between px-6 py-4"
        >
          <h2 style={{ color: 'var(--text-primary)' }} className="text-lg font-bold">Delivery Payload</h2>
          <button
            onClick={onClose}
            style={{ color: 'var(--text-tertiary)' }}
            className="hover:opacity-80 text-sm"
          >
            Close
          </button>
        </div>
        <div className="p-6 overflow-y-auto flex-1">
          <div className="mb-3 flex items-center gap-2">
            <span
              style={{ background: `var(${colors.bg})`, color: `var(${colors.text})` }}
              className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
            >
              {delivery.status}
            </span>
            <span style={{ color: 'var(--text-secondary)' }} className="text-sm">{delivery.delivery_type}</span>
          </div>
          {delivery.error_message && (
            <div
              style={{ background: 'var(--red-subtle)', border: '1px solid var(--red)', color: 'var(--red)' }}
              className="mb-3 p-3 rounded-lg text-sm"
            >
              {delivery.error_message}
            </div>
          )}
          <pre
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            className="rounded-lg p-4 text-xs overflow-x-auto whitespace-pre-wrap"
          >
            {delivery.payload ? JSON.stringify(delivery.payload, null, 2) : 'No payload'}
          </pre>
        </div>
      </div>
    </div>
  )
}

export default function DeliveriesPage() {
  const [deliveries, setDeliveries] = useState<Delivery[]>([])
  const [loading, setLoading] = useState(true)
  const [viewingDelivery, setViewingDelivery] = useState<Delivery | null>(null)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      api.deliveries
        .list(session.access_token)
        .then((data) => {
          setDeliveries(data)
          setLoading(false)
        })
        .catch(() => setLoading(false))
    })
  }, [])

  return (
    <div>
      <h1
        style={{ color: 'var(--text-primary)' }}
        className="text-2xl font-semibold tracking-tight mb-6"
      >
        Deliveries
      </h1>

      {viewingDelivery && (
        <PayloadModal
          delivery={viewingDelivery}
          onClose={() => setViewingDelivery(null)}
        />
      )}

      {loading ? (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-tertiary)' }}
          className="rounded-xl p-8 text-center animate-pulse"
        >
          Loading...
        </div>
      ) : deliveries.length === 0 ? (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          className="rounded-xl p-8 text-center text-sm"
        >
          No deliveries yet — digests will appear here after your first weekly send.
        </div>
      ) : (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
          className="rounded-xl overflow-hidden"
        >
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Type</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Status</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Delivered At</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {deliveries.map((d) => {
                const colors = STATUS_BADGE[d.status] ?? STATUS_BADGE.pending
                return (
                  <tr
                    key={d.id}
                    style={{ borderBottom: '1px solid var(--border-subtle)' }}
                    className="hover:opacity-80 transition-opacity"
                  >
                    <td style={{ color: 'var(--text-secondary)' }} className="px-4 py-3">{d.delivery_type}</td>
                    <td className="px-4 py-3">
                      <span
                        style={{ background: `var(${colors.bg})`, color: `var(${colors.text})` }}
                        className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                      >
                        {d.status}
                      </span>
                    </td>
                    <td style={{ color: 'var(--text-tertiary)' }} className="px-4 py-3">{formatDate(d.delivered_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setViewingDelivery(d)}
                        style={{ color: 'var(--accent-text)' }}
                        className="text-xs hover:underline font-medium"
                      >
                        View
                      </button>
                    </td>
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
