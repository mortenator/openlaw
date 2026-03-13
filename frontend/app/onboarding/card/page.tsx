'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'

const PRACTICE_AREAS = [
  'M&A',
  'Tech Transactions',
  'PE/VC',
  'Infrastructure',
  'Real Estate',
  'Finance & Credit',
  'Litigation',
  'Other',
]

export default function OnboardingCardPage() {
  const router = useRouter()
  const [token, setToken] = useState<string | null>(null)
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [firm, setFirm] = useState('')
  const [role, setRole] = useState('')
  const [practiceAreas, setPracticeAreas] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) setToken(session.access_token)
    })
  }, [])

  const canContinue = !!token && firstName.trim() !== '' && lastName.trim() !== '' && firm.trim() !== ''

  function togglePracticeArea(area: string) {
    setPracticeAreas((prev) =>
      prev.includes(area) ? prev.filter((a) => a !== area) : [...prev, area]
    )
  }

  async function handleSubmit() {
    if (!token || !canContinue) return
    setLoading(true)
    setError('')
    try {
      await api.onboarding.card(token, {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        firm: firm.trim(),
        role: role.trim() || undefined,
        practice_area: practiceAreas,
      })
      router.push('/onboarding/chat')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F8F7F5]">
      <div className="bg-white shadow-xl rounded-2xl max-w-md w-full p-8 mx-4">
        {/* Wordmark */}
        <div className="text-[10px] font-semibold tracking-[0.2em] uppercase text-[#1B3A5C] mb-8">
          OpenLaw
        </div>

        <h1 className="text-2xl font-light text-gray-900 mb-1">Welcome to OpenLaw</h1>
        <p className="text-sm text-gray-400 mb-8">Let&apos;s build your profile.</p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Name row */}
        <div className="flex gap-3 mb-4">
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-400 mb-1">First Name</label>
            <input
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#1B3A5C] focus:border-[#1B3A5C]"
              placeholder="Jordan"
            />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-400 mb-1">Last Name</label>
            <input
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#1B3A5C] focus:border-[#1B3A5C]"
              placeholder="Smith"
            />
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-400 mb-1">Firm</label>
          <input
            type="text"
            value={firm}
            onChange={(e) => setFirm(e.target.value)}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#1B3A5C] focus:border-[#1B3A5C]"
            placeholder="Kirkland & Ellis"
          />
        </div>

        <div className="mb-6">
          <label className="block text-xs font-medium text-gray-400 mb-1">Title / Role</label>
          <input
            type="text"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-1 focus:ring-[#1B3A5C] focus:border-[#1B3A5C]"
            placeholder="Partner, M&A"
          />
        </div>

        {/* Practice areas */}
        <div className="mb-8">
          <label className="block text-xs font-medium text-gray-400 mb-2">Practice Area</label>
          <div className="flex flex-wrap gap-2">
            {PRACTICE_AREAS.map((area) => {
              const selected = practiceAreas.includes(area)
              return (
                <button
                  key={area}
                  onClick={() => togglePracticeArea(area)}
                  className={`rounded-full px-3 py-1 text-sm transition-colors ${
                    selected
                      ? 'bg-[#1B3A5C] text-white border border-[#1B3A5C]'
                      : 'border border-[#1B3A5C]/30 text-gray-700 hover:border-[#1B3A5C]/60'
                  }`}
                >
                  {area}
                </button>
              )
            })}
          </div>
        </div>

        {/* Continue */}
        <div className="flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={!canContinue || loading}
            className="bg-[#1B3A5C] text-white px-6 py-3 rounded-lg text-sm font-medium transition-opacity disabled:opacity-40 hover:opacity-90"
          >
            {loading ? 'Saving…' : 'Continue →'}
          </button>
        </div>
      </div>
    </div>
  )
}
