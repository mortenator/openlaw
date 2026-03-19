'use client'
export const dynamic = "force-dynamic"

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { Company } from '@/lib/types'

export default function CompaniesPage() {
  const [token, setToken] = useState<string | null>(null)
  const [companies, setCompanies] = useState<Company[]>([])
  const [watchlistOnly, setWatchlistOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', industry: '', tags: '', is_watchlist: false })

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)
      api.companies.list(t).then((data) => {
        setCompanies(data)
        setLoading(false)
      }).catch(() => setLoading(false))
    })
  }, [])

  const filtered = watchlistOnly ? companies.filter((c) => c.is_watchlist) : companies

  const [createError, setCreateError] = useState('')

  async function handleCreate() {
    if (!token) return
    setCreateError('')
    try {
      const created = await api.companies.create(token, {
        ...form,
        tags: form.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
      })
      setCompanies((prev) => [...prev, created])
      setShowForm(false)
      setForm({ name: '', industry: '', tags: '', is_watchlist: false })
    } catch (err: unknown) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create company')
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 style={{ color: 'var(--text-primary)' }} className="text-2xl font-semibold tracking-tight">Companies</h1>
        <div className="flex gap-3">
          <div
            style={{ border: '1px solid var(--border)' }}
            className="flex rounded-lg overflow-hidden text-sm"
          >
            <button
              onClick={() => setWatchlistOnly(false)}
              style={{
                background: !watchlistOnly ? 'var(--accent)' : 'var(--bg-elevated)',
                color: !watchlistOnly ? '#fff' : 'var(--text-secondary)',
              }}
              className="px-4 py-2 transition-colors"
            >
              All
            </button>
            <button
              onClick={() => setWatchlistOnly(true)}
              style={{
                background: watchlistOnly ? 'var(--accent)' : 'var(--bg-elevated)',
                color: watchlistOnly ? '#fff' : 'var(--text-secondary)',
                borderLeft: '1px solid var(--border)',
              }}
              className="px-4 py-2 transition-colors"
            >
              Watchlist Only
            </button>
          </div>
          <button
            onClick={() => setShowForm(!showForm)}
            style={{ background: 'var(--accent)' }}
            className="px-4 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity"
          >
            Add Company
          </button>
        </div>
      </div>

      {createError && (
        <div
          style={{ background: 'var(--red-subtle)', border: '1px solid var(--red)', color: 'var(--red)' }}
          className="mb-4 p-3 rounded-lg text-sm"
        >
          {createError}
        </div>
      )}

      {showForm && (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
          className="rounded-xl p-4 mb-4 flex gap-3 flex-wrap"
        >
          <input
            placeholder="Name *"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            className="px-3 py-2 rounded-lg text-sm"
          />
          <input
            placeholder="Industry"
            value={form.industry}
            onChange={(e) => setForm({ ...form, industry: e.target.value })}
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            className="px-3 py-2 rounded-lg text-sm"
          />
          <input
            placeholder="Tags (comma-separated)"
            value={form.tags}
            onChange={(e) => setForm({ ...form, tags: e.target.value })}
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            className="px-3 py-2 rounded-lg text-sm"
          />
          <label style={{ color: 'var(--text-secondary)' }} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_watchlist}
              onChange={(e) => setForm({ ...form, is_watchlist: e.target.checked })}
            />
            Watchlist
          </label>
          <button
            onClick={handleCreate}
            style={{ background: 'var(--accent)' }}
            className="px-4 py-2 text-white text-sm rounded-lg hover:opacity-90 transition-opacity"
          >
            Create
          </button>
        </div>
      )}

      {loading ? (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-tertiary)' }}
          className="rounded-xl p-8 text-center animate-pulse"
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
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Industry</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Tags</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Watchlist</th>
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
                  <td style={{ color: 'var(--text-secondary)' }} className="px-4 py-3">{c.industry ?? '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {(c.tags ?? []).map((tag) => (
                        <span
                          key={tag}
                          style={{ background: 'var(--surface)', color: 'var(--text-secondary)' }}
                          className="px-2 py-0.5 rounded-full text-xs"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {c.is_watchlist && (
                      <span style={{ color: 'var(--green)' }} className="font-medium">✓</span>
                    )}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={4} style={{ color: 'var(--text-tertiary)' }} className="px-4 py-8 text-center">
                    No companies found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
