'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

const BOOT_ITEMS = [
  'Building your profile',
  'Configuring market radar',
  'Setting up relationship monitor',
  'Scheduling your first brief',
]

export default function OnboardingBootingPage() {
  const router = useRouter()
  const [visibleCount, setVisibleCount] = useState(0)

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = []

    // Start revealing items 500ms after mount, 400ms apart
    BOOT_ITEMS.forEach((_, i) => {
      timers.push(
        setTimeout(() => {
          setVisibleCount(i + 1)
        }, 500 + i * 400)
      )
    })

    // After all items visible: 500 + 3*400 + 1500 = 3400ms total
    const finalDelay = 500 + (BOOT_ITEMS.length - 1) * 400 + 1500
    timers.push(
      setTimeout(() => {
        router.push('/dashboard')
      }, finalDelay)
    )

    return () => timers.forEach(clearTimeout)
  }, [router])

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
          <p
            className="text-white/40 text-sm transition-opacity duration-700"
            style={{ opacity: visibleCount >= BOOT_ITEMS.length ? 1 : 0 }}
          >
            You&apos;ll hear from me tomorrow morning.
          </p>
        )}
      </div>
    </div>
  )
}
