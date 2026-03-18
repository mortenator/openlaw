'use client'
export const dynamic = "force-dynamic"

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

function PayloadModal({
  delivery,
  onClose,
}: {
  delivery: Delivery
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl border border-gray-200 shadow-lg w-full max-w-lg max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-bold text-gray-900">Delivery Payload</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-sm"
          >
            Close
          </button>
        </div>
        <div className="p-6 overflow-y-auto flex-1">
          <div className="mb-3 flex items-center gap-2">
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                STATUS_BADGE[delivery.status] ?? STATUS_BADGE.pending
              }`}
            >
              {delivery.status}
            </span>
            <span className="text-sm text-gray-500">{delivery.delivery_type}</span>
          </div>
          {delivery.error_message && (
            <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {delivery.error_message}
            </div>
          )}
          <pre className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-xs text-gray-700 overflow-x-auto whitespace-pre-wrap">
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
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Deliveries</h1>

      {viewingDelivery && (
        <PayloadModal
          delivery={viewingDelivery}
          onClose={() => setViewingDelivery(null)}
        />
      )}

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
                <th className="text-right px-4 py-3 font-medium text-gray-500"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {deliveries.map((d) => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-700">{d.delivery_type}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        STATUS_BADGE[d.status] ?? STATUS_BADGE.pending
                      }`}
                    >
                      {d.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatDate(d.delivered_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setViewingDelivery(d)}
                      className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                    >
                      View
                    </button>
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
