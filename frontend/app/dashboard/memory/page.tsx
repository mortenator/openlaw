'use client'
export const dynamic = "force-dynamic"

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

  const [saveError, setSaveError] = useState('')

  async function handleSave() {
    if (!token) return
    setSaving(true)
    setSaveError('')
    try {
      await api.agentConfigs.update(token, activeTab, configs[activeTab] ?? '')
      setSavedMsg('Saved!')
      setTimeout(() => setSavedMsg(''), 2000)
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <h1
        style={{ color: 'var(--text-primary)' }}
        className="text-2xl font-bold mb-4"
      >
        Memory & Configuration
      </h1>

      <div style={{ borderBottom: '1px solid var(--border)' }} className="flex mb-4">
        {FILE_NAMES.map((name) => (
          <button
            key={name}
            onClick={() => setActiveTab(name)}
            style={{
              borderBottomColor: activeTab === name ? 'var(--accent)' : 'transparent',
              color: activeTab === name ? 'var(--accent-text)' : 'var(--text-tertiary)',
            }}
            className="px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors hover:opacity-80"
          >
            {name}
          </button>
        ))}
      </div>

      {loading ? (
        <div
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
          className="flex-1 rounded-xl p-4 animate-pulse"
        />
      ) : (
        <>
          <textarea
            value={configs[activeTab] ?? ''}
            onChange={(e) => setConfigs({ ...configs, [activeTab]: e.target.value })}
            style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            className="flex-1 w-full px-4 py-3 rounded-xl text-sm font-mono resize-none min-h-[400px]"
          />
          {saveError && (
            <div
              style={{ background: 'var(--red-subtle)', border: '1px solid var(--red)', color: 'var(--red)' }}
              className="mt-2 p-3 rounded-lg text-sm"
            >
              {saveError}
            </div>
          )}
          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={handleSave}
              disabled={saving}
              style={{ background: 'var(--accent)' }}
              className="px-6 py-2 text-white text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
            {savedMsg && (
              <span style={{ color: 'var(--green)' }} className="text-sm font-medium">{savedMsg}</span>
            )}
          </div>
        </>
      )}
    </div>
  )
}
