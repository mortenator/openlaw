'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'

interface StatusRow {
  label: string
  value: string
}

interface OnboardingCard {
  first_name?: string
  last_name?: string
  firm?: string
  practice_area?: string | string[]
}

interface OnboardingAnswers {
  card?: OnboardingCard
  '1'?: string[]
  '2'?: string
  '3'?: string
  '4'?: string
  '5'?: string | string[]
  [key: string]: unknown
}

const STEP = {
  DEAL_TYPES: '1',
  GEOGRAPHY: '2',
  COMPANIES: '3',
  FIRST_FLAG: '4',
  DELIVERY: '5',
} as const

function extractRows(answers: OnboardingAnswers): StatusRow[] {
  const card = answers.card || {}
  const firstName = card.first_name || ''
  const lastName = card.last_name || ''
  const fullName = [firstName, lastName].filter(Boolean).join(' ') || '—'

  const firm = card.firm || '—'

  const practiceArea = Array.isArray(card.practice_area)
    ? card.practice_area.join(' · ')
    : (card.practice_area as string) || '—'
  const rawDealTypes = answers[STEP.DEAL_TYPES]
  const dealTypes = Array.isArray(rawDealTypes) ? rawDealTypes.join(' · ') : '—'
  const focus = [practiceArea, dealTypes].filter(v => v !== '—').join(' · ') || '—'

  const geography = answers[STEP.GEOGRAPHY] || '—'
  const companies = answers[STEP.COMPANIES] || '—'
  const rawDelivery = answers[STEP.DELIVERY]
  const delivery = Array.isArray(rawDelivery)
    ? rawDelivery[0] || 'Morning brief'
    : rawDelivery || 'Morning brief'
  const firstFlag = answers[STEP.FIRST_FLAG] || '—'

  return [
    { label: 'Set up for', value: fullName },
    { label: 'Firm', value: firm },
    { label: 'Focus', value: focus },
    { label: 'Based in', value: geography },
    { label: 'Watching', value: companies },
    { label: 'Delivery', value: delivery },
    { label: 'First flag', value: firstFlag },
  ]
}

export default function OnboardingConfirmPage() {
  const router = useRouter()
  const [token, setToken] = useState<string | null>(null)
  const [rows, setRows] = useState<StatusRow[]>([])
  const [loading, setLoading] = useState(true)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)
      try {
        const status = await api.onboarding.status(t)
        setRows(extractRows(status.answers))
      } catch {
        setError('Could not load your profile. You can still confirm below.')
      } finally {
        setLoading(false)
      }
    })
  }, [])

  async function handleConfirm() {
    if (!token) return
    setConfirming(true)
    setError('')
    try {
      await api.onboarding.confirm(token)
      router.push('/onboarding/booting')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
      setConfirming(false)
    }
  }

  function handleEdit() {
    router.push('/onboarding/chat')
  }

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-start justify-center px-4">
      <div className="bg-white/5 border border-white/10 rounded-2xl max-w-md w-full mt-16 p-8">
        <div className="text-white font-light text-lg mb-6">✦ Your OpenLaw Agent</div>

        {error && (
          <div className="mb-4 p-3 bg-red-900/30 border border-red-500/30 rounded-lg text-sm text-red-400">
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5, 6, 7].map((i) => (
              <div key={i} className="h-5 bg-white/10 rounded animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {rows.map(({ label, value }) => (
              <div key={label} className="flex gap-4">
                <span className="text-white/40 text-sm w-24 flex-shrink-0">{label}:</span>
                <span className="text-white/90 text-sm">{value}</span>
              </div>
            ))}
          </div>
        )}

        <div className="border-t border-white/10 my-6" />

        <div className="flex items-center justify-between">
          <button
            onClick={handleEdit}
            disabled={confirming}
            className="text-white/50 text-sm hover:text-white/80 transition-colors disabled:opacity-40"
          >
            ← Edit
          </button>
          <button
            onClick={handleConfirm}
            disabled={confirming || loading}
            className="bg-[#1B3A5C] text-white px-6 py-3 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-40"
          >
            {confirming ? 'Saving…' : 'Looks good →'}
          </button>
        </div>
      </div>
    </div>
  )
}
