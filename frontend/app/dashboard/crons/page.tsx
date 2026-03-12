'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { UserCron } from '@/lib/types'

function formatDate(d: string | null) {
  if (!d) return 'Never'
  return new Date(d).toLocaleString()
}

export default function CronsPage() {
  const [token, setToken] = useState<string | null>(null)
  const [crons, setCrons] = useState<UserCron[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)
      api.crons.list(t).then((data) => {
        setCrons(data)
        setLoading(false)
      }).catch(() => setLoading(false))
    })
  }, [])

  async function handleToggle(cron: UserCron) {
    if (!token) return
    const updated = await api.crons.toggle(token, cron.id, !cron.is_enabled)
    setCrons((prev) => prev.map((c) => (c.id === cron.id ? updated : c)))
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Scheduled Jobs</h1>

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
