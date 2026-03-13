'use client'

import { useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        router.push('/login')
        return
      }
      // /booting manages its own redirect after animation
      if (pathname === '/onboarding/booting') return
      try {
        const status = await api.onboarding.status(session.access_token)
        if (status.complete) {
          router.push('/dashboard')
        }
      } catch {
        // If status check fails, continue with onboarding
      }
    })
  }, [router, pathname])

  return <>{children}</>
}
