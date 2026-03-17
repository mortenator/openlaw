'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import type { AgentConfig } from '@/lib/types'

const FILE_NAMES: AgentConfig['file_name'][] = [
  'SOUL.md',
  'USER.md',
  'AGENTS.md',
  'MEMORY.md',
  'HEARTBEAT.md',
]

export default function MemoryPage() {
  const [token, setToken] = useState<string | null>(null)
  const [configs, setConfigs] = useState<Record<string, string>>({})
  const [activeTab, setActiveTab] = useState<AgentConfig['file_name']>('SOUL.md')
  const [saving, setSaving] = useState(false)
  const [savedMsg, setSavedMsg] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)
      api.agentConfigs.list(t).then((data) => {
        const map: Record<string, string> = {}
        data.forEach((c) => { map[c.file_name] = c.content })
        setConfigs(map)
        setLoading(false)
      }).catch(() => setLoading(false))
    })
  }, [])

  async function handleSave() {
    if (!token) return
    setSaving(true)
    try {
      await api.agentConfigs.update(token, activeTab, configs[activeTab] ?? '')
      setSavedMsg('Saved!')
      setTimeout(() => setSavedMsg(''), 2000)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Memory & Configuration</h1>

      <div className="flex border-b border-gray-200 mb-4">
        {FILE_NAMES.map((name) => (
          <button
            key={name}
            onClick={() => setActiveTab(name)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === name
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {name}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex-1 bg-white rounded-xl border border-gray-200 p-4 animate-pulse" />
      ) : (
        <>
          <textarea
            value={configs[activeTab] ?? ''}
            onChange={(e) => setConfigs({ ...configs, [activeTab]: e.target.value })}
            className="flex-1 w-full px-4 py-3 border border-gray-300 rounded-xl text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[400px]"
          />
          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
            {savedMsg && (
              <span className="text-sm text-green-600 font-medium">{savedMsg}</span>
            )}
          </div>
        </>
      )}
    </div>
  )
}
