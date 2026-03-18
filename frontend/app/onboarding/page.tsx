'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
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
  'Cross-border',
  'AI / Data',
  'Other',
]

const TOTAL_STEPS = 5

// ---------------------------------------------------------------------------
// Step components
// ---------------------------------------------------------------------------

function StepWelcome({ onNext }: { onNext: () => void }) {
  return (
    <div className="text-center">
      <div className="bg-[#1B3A5C] rounded-full w-16 h-16 flex items-center justify-center text-2xl mx-auto mb-6">
        ⚡
      </div>
      <h2 className="text-2xl font-light text-gray-800 mb-3">
        Welcome to <span className="font-normal text-[#1B3A5C]">OpenLaw</span>
      </h2>
      <p className="text-gray-500 text-sm mb-8 max-w-md mx-auto leading-relaxed">
        Let&apos;s set up your agent in a few quick steps. We&apos;ll ask about your
        practice, the companies you track, and optionally import your contacts.
      </p>
      <button
        onClick={onNext}
        className="bg-[#1B3A5C] text-white px-8 py-3 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
      >
        Get started
      </button>
    </div>
  )
}

function StepPracticeArea({
  initial,
  onNext,
}: {
  initial: string[]
  onNext: (selected: string[]) => void
}) {
  const [selected, setSelected] = useState<string[]>(initial)

  function toggle(area: string) {
    setSelected((prev) =>
      prev.includes(area) ? prev.filter((a) => a !== area) : [...prev, area]
    )
  }

  return (
    <div>
      <h2 className="text-xl font-light text-gray-800 mb-2">Practice Areas</h2>
      <p className="text-gray-500 text-sm mb-6">
        Select the areas that describe your practice.
      </p>
      <div className="flex flex-wrap gap-2 mb-6">
        {PRACTICE_AREAS.map((area) => (
          <button
            key={area}
            onClick={() => toggle(area)}
            className={`rounded-full px-4 py-2 text-sm transition-colors cursor-pointer ${
              selected.includes(area)
                ? 'bg-[#1B3A5C] text-white'
                : 'border border-[#1B3A5C]/30 text-gray-600 hover:border-[#1B3A5C]/60'
            }`}
          >
            {area}
          </button>
        ))}
      </div>
      <button
        onClick={() => onNext(selected)}
        disabled={selected.length === 0}
        className="bg-[#1B3A5C] text-white px-6 py-3 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-30 disabled:cursor-not-allowed"
      >
        Continue
      </button>
    </div>
  )
}

function StepTargetCompanies({
  initial,
  onNext,
}: {
  initial: string
  onNext: (companies: string) => void
}) {
  const [value, setValue] = useState(initial)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  return (
    <div>
      <h2 className="text-xl font-light text-gray-800 mb-2">Target Companies</h2>
      <p className="text-gray-500 text-sm mb-6">
        List 5-10 companies you want to monitor. Separate with commas.
      </p>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={4}
        placeholder="Acme Corp, GlobalTech, Meridian Partners, ..."
        className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-[#1B3A5C]/30 resize-none mb-4"
      />
      <button
        onClick={() => onNext(value.trim())}
        disabled={!value.trim()}
        className="bg-[#1B3A5C] text-white px-6 py-3 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-30 disabled:cursor-not-allowed"
      >
        Continue
      </button>
    </div>
  )
}

function StepContactImport({
  onNext,
}: {
  onNext: (csvText: string) => void
}) {
  const [csvText, setCsvText] = useState('')
  const [fileName, setFileName] = useState('')
  const [parsePreview, setParsePreview] = useState<string[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setFileName(file.name)

    const reader = new FileReader()
    reader.onload = (ev) => {
      const text = ev.target?.result as string
      setCsvText(text)

      // Quick preview: extract names from first few rows
      const lines = text.split('\n').filter((l) => l.trim())
      const preview: string[] = []
      for (let i = 1; i < Math.min(lines.length, 6); i++) {
        const parts = lines[i].split(',')
        if (parts[0]?.trim()) preview.push(parts[0].trim())
      }
      setParsePreview(preview)
    }
    reader.readAsText(file)
  }

  return (
    <div>
      <h2 className="text-xl font-light text-gray-800 mb-2">Import Contacts</h2>
      <p className="text-gray-500 text-sm mb-6">
        Upload a CSV with columns: <span className="font-medium">Name, Email, Company, Role</span>.
        You can also skip this step.
      </p>

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        onChange={handleFileChange}
        className="hidden"
      />

      <button
        onClick={() => fileInputRef.current?.click()}
        className="w-full border-2 border-dashed border-gray-300 rounded-lg py-8 px-4 text-center hover:border-[#1B3A5C]/40 transition-colors cursor-pointer mb-4"
      >
        {fileName ? (
          <div>
            <span className="text-sm text-[#1B3A5C] font-medium">{fileName}</span>
            {parsePreview.length > 0 && (
              <div className="mt-2 text-xs text-gray-400">
                Preview: {parsePreview.join(', ')}
                {parsePreview.length >= 5 && '...'}
              </div>
            )}
          </div>
        ) : (
          <div>
            <div className="text-gray-400 text-sm mb-1">Click to upload CSV</div>
            <div className="text-gray-300 text-xs">or drag and drop</div>
          </div>
        )}
      </button>

      <div className="flex gap-3">
        <button
          onClick={() => onNext('')}
          className="text-sm text-gray-500 hover:text-gray-700 transition-colors py-3 px-4"
        >
          Skip for now
        </button>
        <button
          onClick={() => onNext(csvText)}
          disabled={!csvText}
          className="bg-[#1B3A5C] text-white px-6 py-3 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Upload & Continue
        </button>
      </div>
    </div>
  )
}

function StepConfirmation({
  summary,
  onComplete,
  loading,
}: {
  summary: { practice_areas: string[]; target_companies: string[]; contacts_count: number } | null
  onComplete: () => void
  loading: boolean
}) {
  return (
    <div>
      <h2 className="text-xl font-light text-gray-800 mb-2">Confirm Setup</h2>
      <p className="text-gray-500 text-sm mb-6">
        Review your setup and click Complete to start your agent.
      </p>

      {summary && (
        <div className="bg-white border border-gray-200 rounded-lg p-5 mb-6 space-y-4">
          <div>
            <span className="text-xs text-gray-400 uppercase tracking-wide">Practice Areas</span>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {summary.practice_areas.map((area) => (
                <span
                  key={area}
                  className="bg-[#1B3A5C]/10 text-[#1B3A5C] text-xs rounded-full px-2.5 py-1"
                >
                  {area}
                </span>
              ))}
            </div>
          </div>

          <div>
            <span className="text-xs text-gray-400 uppercase tracking-wide">Target Companies</span>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {summary.target_companies.map((company) => (
                <span
                  key={company}
                  className="bg-gray-100 text-gray-700 text-xs rounded-full px-2.5 py-1"
                >
                  {company}
                </span>
              ))}
            </div>
          </div>

          <div>
            <span className="text-xs text-gray-400 uppercase tracking-wide">Contacts</span>
            <p className="text-sm text-gray-700 mt-1">
              {summary.contacts_count > 0
                ? `${summary.contacts_count} contact${summary.contacts_count === 1 ? '' : 's'} to import`
                : 'No contacts uploaded (you can import later)'}
            </p>
          </div>
        </div>
      )}

      <button
        onClick={onComplete}
        disabled={loading}
        className="bg-[#1B3A5C] text-white px-8 py-3 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-40 w-full"
      >
        {loading ? 'Setting up...' : 'Complete Setup'}
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Progress bar
// ---------------------------------------------------------------------------

function ProgressBar({ step, total }: { step: number; total: number }) {
  const progress = Math.max(0, ((step - 1) / (total - 1)) * 100)

  return (
    <div className="mb-8">
      <div className="flex justify-between text-xs text-gray-400 mb-2">
        <span>Step {step} of {total}</span>
      </div>
      <div className="h-1 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-[#1B3A5C] rounded-full transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function OnboardingPage() {
  const router = useRouter()
  const [token, setToken] = useState<string | null>(null)
  const [currentStep, setCurrentStep] = useState(1)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // Step-specific state
  const [practiceAreas, setPracticeAreas] = useState<string[]>([])
  const [companies, setCompanies] = useState('')
  const [summary, setSummary] = useState<{
    practice_areas: string[]
    target_companies: string[]
    contacts_count: number
  } | null>(null)

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) return
      const t = session.access_token
      setToken(t)

      // Resume from saved progress
      try {
        const status = await api.onboarding.status(t)
        if (status.step > 0 && !status.complete) {
          setCurrentStep(status.step)
          // Restore local state from saved answers
          const answers = status.answers
          if (answers.step_2 && Array.isArray(answers.step_2)) {
            setPracticeAreas(answers.step_2 as string[])
          }
          if (answers.step_3 && typeof answers.step_3 === 'string') {
            setCompanies(answers.step_3 as string)
          }
        }
      } catch {
        // Start fresh
      }
    })
  }, [])

  const submitStep = useCallback(
    async (step: number, answer: unknown) => {
      if (!token) return null
      setError('')
      setLoading(true)
      try {
        const res = await api.onboarding.step(token, step, answer)
        setLoading(false)
        return res
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Something went wrong')
        setLoading(false)
        return null
      }
    },
    [token]
  )

  async function handleWelcomeNext() {
    const res = await submitStep(1, null)
    if (res) setCurrentStep(res.step)
  }

  async function handlePracticeAreaNext(selected: string[]) {
    setPracticeAreas(selected)
    const res = await submitStep(2, selected)
    if (res) setCurrentStep(res.step)
  }

  async function handleCompaniesNext(value: string) {
    setCompanies(value)
    const res = await submitStep(3, value)
    if (res) {
      setCurrentStep(res.step)
      if (res.question?.summary) {
        setSummary(res.question.summary)
      }
    }
  }

  async function handleContactImportNext(csvText: string) {
    const res = await submitStep(4, csvText)
    if (res) {
      setCurrentStep(res.step)
      if (res.question?.summary) {
        setSummary(res.question.summary)
      }
    }
  }

  async function handleComplete() {
    const res = await submitStep(5, null)
    if (res?.complete) {
      router.push('/onboarding/booting')
    }
  }

  return (
    <div className="min-h-screen bg-[#F8F7F5] flex items-start justify-center px-4 pt-16 pb-16">
      <div className="w-full max-w-lg">
        {currentStep > 1 && <ProgressBar step={currentStep} total={TOTAL_STEPS} />}

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
            {error}
          </div>
        )}

        {currentStep === 1 && <StepWelcome onNext={handleWelcomeNext} />}

        {currentStep === 2 && (
          <StepPracticeArea initial={practiceAreas} onNext={handlePracticeAreaNext} />
        )}

        {currentStep === 3 && (
          <StepTargetCompanies initial={companies} onNext={handleCompaniesNext} />
        )}

        {currentStep === 4 && <StepContactImport onNext={handleContactImportNext} />}

        {currentStep === 5 && (
          <StepConfirmation
            summary={summary}
            onComplete={handleComplete}
            loading={loading}
          />
        )}
      </div>
    </div>
  )
}
