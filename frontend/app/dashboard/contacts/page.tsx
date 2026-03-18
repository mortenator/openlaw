'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { Contact } from '@/lib/types'
import { HealthBadge } from '@/components/HealthBadge'

function TierBadge({ tier }: { tier: number }) {
  const colors = ['', 'bg-purple-100 text-purple-700', 'bg-blue-100 text-blue-700', 'bg-gray-100 text-gray-700']
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${colors[tier] ?? ''}`}>
      T{tier}
    </span>
  )
}

function formatDate(d: string | null) {
  if (!d) return 'Never'
  return new Date(d).toLocaleDateString()
}

export default function ContactsPage() {
  const [token, setToken] = useState<string | null>(null)
  const [contacts, setContacts] = useState<Contact[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState<{ name: string; role: string; email: string; tier: 1 | 2 | 3 }>({ name: '', role: '', email: '', tier: 2 })

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)
      api.contacts.list(t).then((data) => {
        setContacts(data)
        setLoading(false)
      }).catch(() => setLoading(false))
    })
  }, [])

  const filtered = contacts.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase())
  )

  const [createError, setCreateError] = useState('')

  async function handleCreate() {
    if (!token) return
    setCreateError('')
    try {
      const created = await api.contacts.create(token, form)
      setContacts((prev) => [...prev, created])
      setShowModal(false)
      setForm({ name: '', role: '', email: '', tier: 2 as 1 | 2 | 3 })
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create contact')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Contacts</h1>
        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700"
        >
          Add Contact
        </button>
      </div>

      <input
        type="text"
        placeholder="Search contacts..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-4 w-full max-w-xs px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />

      {loading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400 text-sm animate-pulse">
          Loading...
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Name</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Role</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Tier</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Health</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Last Contact</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{c.name}</td>
                  <td className="px-4 py-3 text-gray-600">{c.role ?? '—'}</td>
                  <td className="px-4 py-3">
                    <TierBadge tier={c.tier} />
                  </td>
                  <td className="px-4 py-3">
                    <HealthBadge score={c.health_score} />
                  </td>
                  <td className="px-4 py-3 text-gray-500">{formatDate(c.last_contacted_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/dashboard/contacts/${c.id}`}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      Edit
                    </Link>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                    No contacts found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
            <h2 className="text-lg font-semibold mb-4">Add Contact</h2>
            {createError && (
              <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {createError}
              </div>
            )}
            <div className="space-y-3">
              <input
                placeholder="Name *"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
              <input
                placeholder="Role"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
              <input
                placeholder="Email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
              <select
                value={form.tier}
                onChange={(e) => setForm({ ...form, tier: Number(e.target.value) as 1 | 2 | 3 })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                <option value={1}>Tier 1 — VIP</option>
                <option value={2}>Tier 2 — Active</option>
                <option value={3}>Tier 3 — Dormant</option>
              </select>
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={handleCreate}
                className="flex-1 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
              >
                Create
              </button>
              <button
                onClick={() => setShowModal(false)}
                className="flex-1 py-2 border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
