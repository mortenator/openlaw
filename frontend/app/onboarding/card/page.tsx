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

  const canContinue =
    !!token && firstName.trim() !== '' && lastName.trim() !== '' && firm.trim() !== ''

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
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#F8F7F5] px-6">
      {/* Heading — outside the card, left-aligned */}
      <div className="w-full max-w-xl mb-5">
        <h1 className="text-2xl font-light text-gray-800">
          Welcome to{' '}
          <span className="font-normal text-[#1B3A5C]">OpenLaw</span>
        </h1>
      </div>

      {error && (
        <div className="w-full max-w-xl mb-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Business card — landscape, physical card feel */}
      <div
        className="w-full max-w-xl rounded-2xl shadow-md flex flex-col"
        style={{ backgroundColor: '#ECEAE6', minHeight: '240px' }}
      >
        {/* Top row: firm (top-left) + brand (top-right) */}
        <div className="flex items-start justify-between px-7 pt-6">
          <input
            type="text"
            value={firm}
            onChange={(e) => setFirm(e.target.value)}
            placeholder="Sullivan & Cromwell"
            className="bg-transparent text-sm font-medium text-gray-700 placeholder-gray-400 focus:outline-none border-b border-transparent hover:border-gray-300 focus:border-gray-400 transition-colors pb-px max-w-[200px]"
          />
          <span className="text-xs text-gray-400 tracking-wide select-none">
            ⚡ OpenLaw
          </span>
        </div>

        {/* Middle — empty space like a real business card */}
        <div className="flex-1" style={{ minHeight: '72px' }} />

        {/* Bottom — name + title inputs */}
        <div className="px-7 pb-6">
          {/* Role — lighter, above name */}
          <div className="mb-3">
            <input
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="Partner, M&A"
              className="bg-transparent text-xs text-gray-500 placeholder-gray-400 focus:outline-none w-full"
            />
          </div>
          {/* First / Last name side by side */}
          <div className="flex gap-3">
            <input
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              placeholder="First"
              className="w-1/2 bg-white/70 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-[#1B3A5C]/30"
            />
            <input
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              placeholder="Last"
              className="w-1/2 bg-white/70 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-[#1B3A5C]/30"
            />
          </div>
        </div>
      </div>

      {/* Below card — practice area + continue */}
      <div className="w-full max-w-xl mt-5">
        <p className="text-xs text-gray-400 mb-2 tracking-wide">Practice Area</p>
        <div className="flex flex-wrap gap-2 mb-5">
          {PRACTICE_AREAS.map((area) => {
            const selected = practiceAreas.includes(area)
            return (
              <button
                key={area}
                onClick={() => togglePracticeArea(area)}
                className={`rounded-full px-3 py-1 text-sm transition-colors ${
                  selected
                    ? 'bg-[#1B3A5C] text-white'
                    : 'border border-[#1B3A5C]/30 text-gray-600 hover:border-[#1B3A5C]/60'
                }`}
              >
                {area}
              </button>
            )
          })}
        </div>

        {/* Continue — plain text link, Hebbia style */}
        <button
          onClick={handleSubmit}
          disabled={!canContinue || loading}
          className="text-sm text-gray-700 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Saving…' : 'Continue →'}
        </button>
      </div>
    </div>
  )
}
