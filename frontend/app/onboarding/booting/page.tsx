'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'

const BOOT_ITEMS = [
  'Building your profile',
  'Configuring market radar',
  'Setting up relationship monitor',
  'Scheduling your first brief',
]

// Minimum time to show each item before advancing (ms)
const ITEM_REVEAL_INTERVAL = 400
const ITEM_REVEAL_START_DELAY = 500
// Poll interval for backend readiness (ms)
const POLL_INTERVAL = 1500
// Maximum time to wait for backend before redirecting anyway (ms)
const MAX_WAIT = 15_000
// Initial delay before first poll (give backend time to kick off provisioning)
const INITIAL_POLL_DELAY = 800

export default function OnboardingBootingPage() {
  const router = useRouter()
  const [visibleCount, setVisibleCount] = useState(0)
  const [ready, setReady] = useState(false)
  const startedAt = useRef<number>(0)
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const revealTimers = useRef<ReturnType<typeof setTimeout>[]>([])

  // Reveal items progressively (pure UI cadence, independent of backend)
  useEffect(() => {
    const timers = BOOT_ITEMS.map((_, i) =>
      setTimeout(
        () => setVisibleCount(i + 1),
        ITEM_REVEAL_START_DELAY + i * ITEM_REVEAL_INTERVAL
      )
    )
    revealTimers.current = timers
    return () => timers.forEach(clearTimeout)
  }, [])

  // Poll backend status until complete (or timeout)
  useEffect(() => {
    let cancelled = false

    async function checkReady() {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        if (!session) {
          // No session — just redirect after animations
          if (!cancelled) setReady(true)
          return
        }
        const status = await api.onboarding.status(session.access_token)
        if (!cancelled && status.complete) {
          setReady(true)
          return
        }
      } catch (err) {
        // Keep polling, but surface errors for observability
        console.error('[OnboardingBooting] status poll error:', err)
      }

      if (!cancelled) {
        const elapsed = Date.now() - startedAt.current
        if (elapsed >= MAX_WAIT) {
          // Give up waiting; redirect anyway
          setReady(true)
          return
        }
        pollTimer.current = setTimeout(checkReady, POLL_INTERVAL)
      }
    }

    // Start polling after a short initial delay (give backend time to kick off)
    pollTimer.current = setTimeout(() => {
      startedAt.current = Date.now()
      checkReady()
    }, INITIAL_POLL_DELAY)

    return () => {
      cancelled = true
      if (pollTimer.current) clearTimeout(pollTimer.current)
    }
  }, [])

  // Redirect once BOTH all items are visible AND backend is ready
  useEffect(() => {
    const allItemsVisible = visibleCount >= BOOT_ITEMS.length
    if (allItemsVisible && ready) {
      // Brief pause so the final item feels settled
      const t = setTimeout(() => router.push('/dashboard'), 800)
      return () => clearTimeout(t)
    }
  }, [visibleCount, ready, router])

  return (
    <div className="min-h-screen bg-[#0D0D0D] flex items-center justify-center px-4">
      <div className="max-w-sm w-full">
        <div className="flex items-center gap-3 mb-8">
          <div className="bg-[#1B3A5C] rounded-full w-8 h-8 flex items-center justify-center text-sm animate-pulse">
            ⚡
          </div>
          <span className="text-white/70 text-sm">Spinning up your agent…</span>
        </div>

        <div className="space-y-3 mb-10">
          {BOOT_ITEMS.map((item, i) => (
            <div
              key={item}
              className="flex items-center gap-3 transition-opacity duration-500"
              style={{ opacity: visibleCount > i ? 1 : 0 }}
            >
              <span className="text-[#7B9FC4] text-sm w-4">✓</span>
              <span className="text-white/80 text-sm">{item}</span>
            </div>
          ))}
        </div>

        {visibleCount >= BOOT_ITEMS.length && (
          <p className="text-white/40 text-sm transition-opacity duration-700">
            You&apos;ll hear from me tomorrow morning.
          </p>
        )}
      </div>
    </div>
  )
}
