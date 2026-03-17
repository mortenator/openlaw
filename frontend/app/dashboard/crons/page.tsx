'use client'

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
  { label: 'Monthly 1st 8am', value: '0 8 1 * *' },
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
  userId,
}: {
  onClose: () => void
  onCreated: (cron: UserCron) => void
  token: string
  userId: string
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
      const created = await api.crons.create(token, userId, {
        name: form.name.trim(),
        job_type: form.job_type,
        schedule: form.cron_expression,
        config: { keywords },
        is_enabled: true,
      })
      onCreated(created)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create cron')
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl border border-gray-200 shadow-lg w-full max-w-md p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-4">New Scan</h2>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => updateField('name', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="e.g. Morning market scan"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Job Type</label>
            <select
              value={form.job_type}
              onChange={(e) => updateField('job_type', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              {JOB_TYPES.map((jt) => (
                <option key={jt.value} value={jt.value}>
                  {jt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Schedule</label>
            <div className="space-y-2">
              {SCHEDULE_PRESETS.map((preset) => (
                <label key={preset.value} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="schedule"
                    value={preset.value}
                    checked={form.cron_expression === preset.value}
                    onChange={() => updateField('cron_expression', preset.value)}
                    className="text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{preset.label}</span>
                  <span className="text-xs text-gray-400 font-mono">{preset.value}</span>
                </label>
              ))}
            </div>
          </div>

          {form.job_type === 'market_brief' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Keywords <span className="text-gray-400 font-normal">(comma-separated)</span>
              </label>
              <input
                type="text"
                value={form.keywords}
                onChange={(e) => updateField('keywords', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g. M&A, private equity, restructuring"
              />
            </div>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
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
  const [userId, setUserId] = useState<string | null>(null)
  const [crons, setCrons] = useState<UserCron[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)
      setUserId(session.user.id)
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
    const updated = await api.crons.toggle(token, cron.id, !cron.is_enabled)
    setCrons((prev) => prev.map((c) => (c.id === cron.id ? updated : c)))
  }

  function handleCreated(cron: UserCron) {
    setCrons((prev) => [...prev, cron])
    setShowCreate(false)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Scheduled Jobs</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
        >
          New scan
        </button>
      </div>

      {showCreate && token && userId && (
        <CreateCronModal
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
          token={token}
          userId={userId}
        />
      )}

      {loading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400 animate-pulse">
          Loading...
        </div>
      ) : crons.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-500 text-sm">
          No cron jobs configured
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Name</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Schedule</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Job Type</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Last Run</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {crons.map((cron) => (
                <tr key={cron.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{cron.name}</td>
                  <td className="px-4 py-3 font-mono text-gray-600 text-xs">{cron.schedule}</td>
                  <td className="px-4 py-3 text-gray-600">{cron.job_type}</td>
                  <td className="px-4 py-3 text-gray-500">{formatDate(cron.last_run_at)}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleToggle(cron)}
                      className={`relative inline-flex h-5 w-10 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${
                        cron.is_enabled ? 'bg-blue-600' : 'bg-gray-200'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ${
                          cron.is_enabled ? 'translate-x-5' : 'translate-x-0'
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
