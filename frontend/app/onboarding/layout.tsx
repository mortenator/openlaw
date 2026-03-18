'use client'

import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        router.push('/login')
        return
      }
      // /booting manages its own redirect after animation
      if (pathname === '/onboarding/booting') {
        setChecked(true)
        return
      }
      try {
        const status = await api.onboarding.status(session.access_token)
        if (status.complete) {
          router.push('/dashboard')
          return
        }
      } catch {
        // If status check fails, continue with onboarding
      }
      setChecked(true)
    })
  }, [router, pathname])

  if (!checked) {
    return (
      <div className="min-h-screen bg-[#F8F7F5] flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-[#1B3A5C] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return <>{children}</>
}
