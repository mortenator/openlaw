'use client'
export const dynamic = "force-dynamic"

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { Contact } from '@/lib/types'
import { HealthBadge } from '@/components/HealthBadge'
import { Search, Plus } from 'lucide-react'

function TierBadge({ tier }: { tier: number }) {
  const styles: Record<number, { bg: string; text: string }> = {
    1: { bg: '--purple-subtle', text: '--purple' },
    2: { bg: '--accent-subtle', text: '--accent-text' },
    3: { bg: '--surface', text: '--text-secondary' },
  }
  const s = styles[tier] ?? styles[3]
  return (
    <span
      style={{ background: `var(${s.bg})`, color: `var(${s.text})` }}
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
    >
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
        <h1
          style={{ color: 'var(--text-primary)' }}
          className="text-2xl font-semibold tracking-tight"
        >
          Contacts
        </h1>
        <button
          onClick={() => setShowModal(true)}
          style={{ background: 'var(--accent)' }}
          className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2"
        >
          <Plus size={16} />
          Add Contact
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-4 max-w-xs">
        <Search
          size={16}
          style={{ color: 'var(--text-tertiary)' }}
          className="absolute left-3 top-1/2 -translate-y-1/2"
        />
        <input
          type="text"
          placeholder="Search contacts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            color: 'var(--text-primary)',
          }}
          className="w-full pl-9 pr-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2"
        />
      </div>

      {loading ? (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-tertiary)' }}
          className="rounded-xl p-8 text-center text-sm animate-pulse"
        >
          Loading...
        </div>
      ) : (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
          className="rounded-xl overflow-hidden"
        >
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Name</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Role</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Tier</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Health</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Last Contact</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr
                  key={c.id}
                  style={{ borderBottom: '1px solid var(--border-subtle)' }}
                  className="hover:opacity-80 transition-opacity"
                >
                  <td style={{ color: 'var(--text-primary)' }} className="px-4 py-3 font-medium">{c.name}</td>
                  <td style={{ color: 'var(--text-secondary)' }} className="px-4 py-3">{c.role ?? '—'}</td>
                  <td className="px-4 py-3">
                    <TierBadge tier={c.tier} />
                  </td>
                  <td className="px-4 py-3">
                    <HealthBadge score={c.health_score} />
                  </td>
                  <td style={{ color: 'var(--text-tertiary)' }} className="px-4 py-3">{formatDate(c.last_contacted_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/dashboard/contacts/${c.id}`}
                      style={{ color: 'var(--accent-text)' }}
                      className="hover:underline text-xs"
                    >
                      Edit
                    </Link>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ color: 'var(--text-tertiary)' }} className="px-4 py-8 text-center">
                    No contacts found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Contact Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div
            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
            className="rounded-xl p-6 w-full max-w-md shadow-xl"
          >
            <h2 style={{ color: 'var(--text-primary)' }} className="text-lg font-semibold mb-4">
              Add Contact
            </h2>
            {createError && (
              <div
                style={{ background: 'var(--red-subtle)', color: 'var(--red)' }}
                className="mb-3 p-3 rounded-lg text-sm"
              >
                {createError}
              </div>
            )}
            <div className="space-y-3">
              <input
                placeholder="Name *"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                className="w-full px-3 py-2 rounded-lg text-sm"
              />
              <input
                placeholder="Role"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                className="w-full px-3 py-2 rounded-lg text-sm"
              />
              <input
                placeholder="Email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                className="w-full px-3 py-2 rounded-lg text-sm"
              />
              <select
                value={form.tier}
                onChange={(e) => setForm({ ...form, tier: Number(e.target.value) as 1 | 2 | 3 })}
                style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                className="w-full px-3 py-2 rounded-lg text-sm"
              >
                <option value={1}>Tier 1 — VIP</option>
                <option value={2}>Tier 2 — Active</option>
                <option value={3}>Tier 3 — Dormant</option>
              </select>
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={handleCreate}
                style={{ background: 'var(--accent)' }}
                className="flex-1 py-2 text-white text-sm rounded-lg hover:opacity-90 transition-opacity"
              >
                Create
              </button>
              <button
                onClick={() => setShowModal(false)}
                style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
                className="flex-1 py-2 text-sm rounded-lg hover:opacity-80 transition-opacity"
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
