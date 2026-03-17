'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { Contact } from '@/lib/types'
import { HealthBadge } from '@/components/HealthBadge'

export default function ContactDetailPage({ params }: { params: { id: string } }) {
  const [token, setToken] = useState<string | null>(null)
  const [contact, setContact] = useState<Contact | null>(null)
  const [form, setForm] = useState({
    name: '',
    role: '',
    email: '',
    tier: 2,
    last_contacted_at: '',
    notes: '',
  })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)
      api.contacts.get(t, params.id).then((c) => {
        setContact(c)
        setForm({
          name: c.name,
          role: c.role ?? '',
          email: c.email ?? '',
          tier: c.tier,
          last_contacted_at: c.last_contacted_at
            ? c.last_contacted_at.split('T')[0]
            : '',
          notes: c.notes ?? '',
        })
      }).catch((err: unknown) => {
        setLoadError(err instanceof Error ? err.message : 'Failed to load contact')
      })
    })
  }, [params.id])

  const [saveError, setSaveError] = useState('')

  async function handleSave() {
    if (!token) return
    setSaving(true)
    setSaveError('')
    try {
      const updated = await api.contacts.update(token, params.id, {
        ...form,
        tier: Number(form.tier) as 1 | 2 | 3,
        last_contacted_at: form.last_contacted_at || null,
      })
      setContact(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save contact')
    } finally {
      setSaving(false)
    }
  }

  if (loadError) {
    return <div className="text-red-600 text-sm">{loadError}</div>
  }

  if (!contact) {
    return <div className="text-gray-400 text-sm">Loading...</div>
  }

  return (
    <div className="max-w-xl">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/dashboard/contacts" className="text-sm text-gray-500 hover:text-gray-700">
          ← Contacts
        </Link>
      </div>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{contact.name}</h1>
        <HealthBadge score={contact.health_score} />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
          <input
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Tier</label>
          <select
            value={form.tier}
            onChange={(e) => setForm({ ...form, tier: Number(e.target.value) })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
          >
            <option value={1}>Tier 1 — VIP</option>
            <option value={2}>Tier 2 — Active</option>
            <option value={3}>Tier 3 — Dormant</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Last Contacted</label>
          <input
            type="date"
            value={form.last_contacted_at}
            onChange={(e) => setForm({ ...form, last_contacted_at: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Notes</label>
          <textarea
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            rows={4}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm resize-none"
          />
        </div>

        {saveError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {saveError}
          </div>
        )}

        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {saved ? 'Saved!' : saving ? 'Saving...' : 'Save'}
        </button>
      </div>
    </div>
  )
}
