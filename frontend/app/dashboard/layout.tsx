'use client'
export const dynamic = "force-dynamic"

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import Sidebar from '@/components/layout/Sidebar'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const routerRef = useRef(router)
  routerRef.current = router
  const [ready, setReady] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      if (!session) {
        routerRef.current.push('/login')
        return
      }

      // Check onboarding completion — redirect to onboarding if not done
      try {
        const status = await api.onboarding.status(session.access_token)
        if (!status.complete) {
          routerRef.current.push('/onboarding/card')
          return
        }
      } catch {
        // If the check fails, let them through — don't block the dashboard
      }

      setReady(true)
    }).catch(() => {
      routerRef.current.push('/login')
    })
  }, [])

  if (!ready) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-400 text-sm">Loading...</div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 ml-64 p-8">{children}</main>
    </div>
  )
}
