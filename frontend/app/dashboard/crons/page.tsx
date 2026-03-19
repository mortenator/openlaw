'use client'
export const dynamic = "force-dynamic"

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { UserCron } from '@/lib/types'

const JOB_TYPES = [
  { label: 'Market Brief', value: 'market_brief' },
  { label: 'Relationship Scan', value: 'relationship_scan' },
  { label: 'Weekly Digest', value: 'weekly_digest' },
] as const

const SCHEDULE_PRESETS = [
  { label: 'Daily at 8am', value: '0 8 * * *' },
  { label: 'Weekly Friday 8am', value: '0 8 * * 5' },
  { label: 'Weekly Monday 8am', value: '0 8 * * 1' },
  { label: 'Every 2 hours', value: '0 */2 * * *' },
] as const

interface CreateFormState {
  name: string
  job_type: string
  cron_expression: string
  keywords: string
}

const INITIAL_FORM: CreateFormState = {
  name: '',
  job_type: 'market_brief',
  cron_expression: '0 8 * * *',
  keywords: '',
}

function formatDate(d: string | null) {
  if (!d) return 'Never'
  return new Date(d).toLocaleString()
}

function CreateCronModal({
  onClose,
  onCreated,
  token,
}: {
  onClose: () => void
  onCreated: (cron: UserCron) => void
  token: string
}) {
  const [form, setForm] = useState<CreateFormState>(INITIAL_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  function updateField<K extends keyof CreateFormState>(key: K, value: CreateFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSubmit() {
    if (!form.name.trim()) {
      setError('Name is required')
      return
    }
    setError('')
    setSubmitting(true)
    try {
      const keywords =
        form.job_type === 'market_brief'
          ? form.keywords
              .split(',')
              .map((k) => k.trim())
              .filter(Boolean)
          : []
      const created = await api.crons.create(token, {
        name: form.name.trim(),
        job_type: form.job_type,
        cron_expression: form.cron_expression,
        config: { keywords },
        is_active: true,
      })
      onCreated(created)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create cron')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
        className="rounded-xl shadow-lg w-full max-w-md p-6"
      >
        <h2 style={{ color: 'var(--text-primary)' }} className="text-lg font-bold mb-4">New Scan</h2>

        {error && (
          <div
            style={{ background: 'var(--red-subtle)', border: '1px solid var(--red)', color: 'var(--red)' }}
            className="mb-4 p-3 rounded-lg text-sm"
          >
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label style={{ color: 'var(--text-secondary)' }} className="block text-sm font-medium mb-1">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateField('name', e.target.value)}
              style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
              className="w-full px-3 py-2 rounded-lg text-sm"
              placeholder="e.g. Morning market scan"
            />
          </div>

          <div>
            <label style={{ color: 'var(--text-secondary)' }} className="block text-sm font-medium mb-1">Job Type</label>
            <select
              value={form.job_type}
              onChange={(e) => updateField('job_type', e.target.value)}
              style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
              className="w-full px-3 py-2 rounded-lg text-sm"
            >
              {JOB_TYPES.map((jt) => (
                <option key={jt.value} value={jt.value}>
                  {jt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ color: 'var(--text-secondary)' }} className="block text-sm font-medium mb-2">Schedule</label>
            <div className="space-y-2">
              {SCHEDULE_PRESETS.map((preset) => (
                <label key={preset.value} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="schedule"
                    value={preset.value}
                    checked={form.cron_expression === preset.value}
                    onChange={() => updateField('cron_expression', preset.value)}
                    style={{ accentColor: 'var(--accent)' }}
                  />
                  <span style={{ color: 'var(--text-secondary)' }} className="text-sm">{preset.label}</span>
                  <span style={{ color: 'var(--text-tertiary)' }} className="text-xs font-mono">{preset.value}</span>
                </label>
              ))}
            </div>
          </div>

          {form.job_type === 'market_brief' && (
            <div>
              <label style={{ color: 'var(--text-secondary)' }} className="block text-sm font-medium mb-1">
                Keywords <span style={{ color: 'var(--text-tertiary)' }} className="font-normal">(comma-separated)</span>
              </label>
              <input
                type="text"
                value={form.keywords}
                onChange={(e) => updateField('keywords', e.target.value)}
                style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                className="w-full px-3 py-2 rounded-lg text-sm"
                placeholder="e.g. M&A, private equity, restructuring"
              />
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={submitting}
            style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
            className="px-4 py-2 text-sm font-medium rounded-lg hover:opacity-80 transition-opacity disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            style={{ background: 'var(--accent)' }}
            className="px-4 py-2 text-sm font-medium text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {submitting ? 'Creating...' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function CronsPage() {
  const [token, setToken] = useState<string | null>(null)
  const [crons, setCrons] = useState<UserCron[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)
      api.crons
        .list(t)
        .then((data) => {
          setCrons(data)
          setLoading(false)
        })
        .catch(() => setLoading(false))
    })
  }, [])

  async function handleToggle(cron: UserCron) {
    if (!token) return
    const previous = crons
    setCrons((prev) => prev.map((c) => (c.id === cron.id ? { ...c, is_active: !c.is_active } : c)))
    try {
      const updated = await api.crons.toggle(token, cron.id, !cron.is_active)
      setCrons((prev) => prev.map((c) => (c.id === cron.id ? updated : c)))
    } catch {
      setCrons(previous)
    }
  }

  function handleCreated(cron: UserCron) {
    setCrons((prev) => [...prev, cron])
    setShowCreate(false)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 style={{ color: 'var(--text-primary)' }} className="text-2xl font-bold">Scheduled Jobs</h1>
        <button
          onClick={() => setShowCreate(true)}
          style={{ background: 'var(--accent)' }}
          className="px-4 py-2 text-sm font-medium text-white rounded-lg hover:opacity-90 transition-opacity"
        >
          New scan
        </button>
      </div>

      {showCreate && token && (
        <CreateCronModal
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
          token={token}
        />
      )}

      {loading ? (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-tertiary)' }}
          className="rounded-xl p-8 text-center animate-pulse"
        >
          Loading...
        </div>
      ) : crons.length === 0 ? (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
          className="rounded-xl p-8 text-center text-sm"
        >
          No cron jobs configured
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
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Schedule</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Job Type</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Last Run</th>
                <th style={{ color: 'var(--text-tertiary)' }} className="text-left px-4 py-3 font-medium text-xs uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody>
              {crons.map((cron) => (
                <tr
                  key={cron.id}
                  style={{ borderBottom: '1px solid var(--border-subtle)' }}
                  className="hover:opacity-80 transition-opacity"
                >
                  <td style={{ color: 'var(--text-primary)' }} className="px-4 py-3 font-medium">{cron.name}</td>
                  <td style={{ color: 'var(--text-secondary)' }} className="px-4 py-3 font-mono text-xs">{cron.cron_expression}</td>
                  <td style={{ color: 'var(--text-secondary)' }} className="px-4 py-3">{cron.job_type}</td>
                  <td style={{ color: 'var(--text-tertiary)' }} className="px-4 py-3">{formatDate(cron.last_run_at)}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleToggle(cron)}
                      style={{ background: cron.is_active ? 'var(--accent)' : 'var(--surface)' }}
                      className="relative inline-flex h-5 w-10 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none"
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ${
                          cron.is_active ? 'translate-x-5' : 'translate-x-0'
                        }`}
                      />
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
