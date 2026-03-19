'use client'
export const dynamic = "force-dynamic"

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import { Check } from 'lucide-react'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function redirectAfterAuth(token: string, router: ReturnType<typeof useRouter>) {
  try {
    const status = await api.onboarding.status(token)
    router.push(status.complete ? '/dashboard' : '/onboarding/card')
  } catch {
    router.push('/onboarding/card')
  }
}

const FEATURES = [
  'Proactive relationship radar',
  'Daily market intelligence',
  'Reactive deal research',
]

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSignIn() {
    setError('')
    setLoading(true)
    try {
      const { error, data } = await supabase.auth.signInWithPassword({ email, password })
      if (error) throw error
      const token = data.session?.access_token
      setLoading(false)
      if (token) {
        await redirectAfterAuth(token, router)
      } else {
        router.push('/onboarding/card')
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Sign in failed')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left panel — brand */}
      <div
        style={{ background: 'var(--accent)' }}
        className="hidden lg:flex w-1/2 flex-col justify-center px-16 text-white"
      >
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl font-bold mb-8"
          style={{ background: 'rgba(255,255,255,0.15)' }}
        >
          OL
        </div>
        <h1 className="text-4xl font-bold tracking-tight mb-3">OpenLaw</h1>
        <p className="text-lg opacity-80 mb-10">
          Your AI Chief of Staff. Built for deal lawyers.
        </p>
        <ul className="space-y-4">
          {FEATURES.map((f) => (
            <li key={f} className="flex items-center gap-3 text-sm opacity-90">
              <div className="w-5 h-5 rounded-full flex items-center justify-center" style={{ background: 'rgba(255,255,255,0.2)' }}>
                <Check size={12} />
              </div>
              {f}
            </li>
          ))}
        </ul>
      </div>

      {/* Right panel — form */}
      <div
        style={{ background: 'var(--bg)' }}
        className="flex-1 flex items-center justify-center px-8"
      >
        <div className="w-full max-w-sm">
          {/* Mobile brand (hidden on lg) */}
          <div className="lg:hidden mb-8">
            <div className="flex items-center gap-3 mb-2">
              <div
                style={{ background: 'var(--accent)' }}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-sm font-bold"
              >
                OL
              </div>
              <span style={{ color: 'var(--text-primary)' }} className="text-lg font-bold">OpenLaw</span>
            </div>
            <p style={{ color: 'var(--text-secondary)' }} className="text-sm">AI Chief of Staff for deal lawyers</p>
          </div>

          <h2
            style={{ color: 'var(--text-primary)' }}
            className="text-2xl font-semibold tracking-tight mb-1"
          >
            Welcome back
          </h2>
          <p style={{ color: 'var(--text-secondary)' }} className="text-sm mb-8">
            Sign in to your account
          </p>

          {error && (
            <div
              style={{ background: 'var(--red-subtle)', color: 'var(--red)', border: '1px solid var(--red)' }}
              className="mb-4 p-3 rounded-lg text-sm opacity-80"
            >
              {error}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label
                style={{ color: 'var(--text-secondary)' }}
                className="block text-sm font-medium mb-1.5"
              >
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-primary)',
                }}
                className="w-full px-3.5 py-2.5 rounded-xl text-sm focus:outline-none focus:ring-2"
                placeholder="you@firm.com"
              />
            </div>
            <div>
              <label
                style={{ color: 'var(--text-secondary)' }}
                className="block text-sm font-medium mb-1.5"
              >
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSignIn()}
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-primary)',
                }}
                className="w-full px-3.5 py-2.5 rounded-xl text-sm focus:outline-none focus:ring-2"
                placeholder="••••••••"
              />
            </div>
          </div>

          <div className="mt-6 space-y-3">
            <button
              onClick={handleSignIn}
              disabled={loading}
              style={{ background: 'var(--accent)' }}
              className="w-full py-2.5 px-4 text-white text-sm font-medium rounded-xl hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
            <a
              href="mailto:hello@openlaw.ai"
              style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
              className="w-full py-2.5 px-4 text-sm font-medium rounded-xl hover:opacity-80 transition-opacity block text-center"
            >
              Request Access
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
