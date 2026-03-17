'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { useEffect, useState } from 'react'

const NAV_LINKS = [
  { href: '/dashboard', label: 'Today' },
  { href: '/dashboard/contacts', label: 'Contacts' },
  { href: '/dashboard/companies', label: 'Companies' },
  { href: '/dashboard/signals', label: 'Signals' },
  { href: '/dashboard/memory', label: 'Memory' },
  { href: '/dashboard/crons', label: 'Crons' },
  { href: '/dashboard/deliveries', label: 'Deliveries' },
  { href: '/dashboard/chat', label: 'Chat' },
]

export default function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const [email, setEmail] = useState('')

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.user?.email) setEmail(session.user.email)
    })
  }, [])

  async function handleSignOut() {
    await supabase.auth.signOut()
    router.push('/login')
  }

  return (
    <aside className="w-64 bg-gray-900 text-white flex flex-col h-screen fixed left-0 top-0">
      <div className="px-6 py-5 border-b border-gray-700">
        <div className="text-lg font-bold">OpenLaw</div>
        <div className="text-xs text-gray-400 mt-0.5">AI Chief of Staff</div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_LINKS.map(({ href, label }) => {
          const isActive = pathname === href
          return (
            <Link
              key={href}
              href={href}
              className={`block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              }`}
            >
              {label}
            </Link>
          )
        })}
      </nav>

      <div className="px-4 py-4 border-t border-gray-700">
        <div className="text-xs text-gray-400 truncate mb-2">{email}</div>
        <button
          onClick={handleSignOut}
          className="w-full text-left px-3 py-2 text-sm text-gray-300 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
        >
          Sign Out
        </button>
      </div>
    </aside>
  )
}
