'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'
import { useEffect, useState } from 'react'
import { useTheme } from '@/lib/theme'
import {
  LayoutDashboard,
  Users,
  Building2,
  Zap,
  Brain,
  Clock,
  Mail,
  MessageSquare,
  Sun,
  Moon,
  LogOut,
} from 'lucide-react'

const NAV_LINKS = [
  { href: '/dashboard', label: 'Home', icon: LayoutDashboard },
  { href: '/dashboard/contacts', label: 'Contacts', icon: Users },
  { href: '/dashboard/companies', label: 'Companies', icon: Building2 },
  { href: '/dashboard/signals', label: 'Signals', icon: Zap },
  { href: '/dashboard/memory', label: 'Memory', icon: Brain },
  { href: '/dashboard/crons', label: 'Crons', icon: Clock },
  { href: '/dashboard/deliveries', label: 'Deliveries', icon: Mail },
  { href: '/dashboard/chat', label: 'Chat', icon: MessageSquare },
]

export default function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const { theme, toggle } = useTheme()
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
    <aside
      style={{
        background: 'var(--bg-elevated)',
        borderRight: '1px solid var(--border)',
      }}
      className="w-64 h-screen fixed left-0 top-0 flex flex-col"
    >
      {/* Brand */}
      <div
        style={{ borderBottom: '1px solid var(--border)' }}
        className="px-6 py-5"
      >
        <div className="flex items-center gap-3">
          <div
            style={{ background: 'var(--accent)' }}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-sm font-bold"
          >
            OL
          </div>
          <div>
            <div
              style={{ color: 'var(--text-primary)' }}
              className="text-sm font-bold tracking-tight"
            >
              OpenLaw
            </div>
            <div
              style={{ color: 'var(--text-tertiary)' }}
              className="text-xs"
            >
              AI Chief of Staff
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV_LINKS.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href
          return (
            <Link
              key={href}
              href={href}
              style={{
                background: isActive ? 'var(--accent-subtle)' : 'transparent',
                color: isActive ? 'var(--accent-text)' : 'var(--text-secondary)',
              }}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80"
            >
              <Icon size={16} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Bottom */}
      <div
        style={{ borderTop: '1px solid var(--border)' }}
        className="px-4 py-4 space-y-3"
      >
        {/* Theme toggle */}
        <button
          onClick={toggle}
          style={{
            background: 'var(--surface)',
            color: 'var(--text-secondary)',
          }}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
        </button>

        {/* User */}
        <div
          style={{ color: 'var(--text-tertiary)' }}
          className="text-xs truncate px-3"
        >
          {email}
        </div>

        <button
          onClick={handleSignOut}
          style={{ color: 'var(--text-secondary)' }}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80"
        >
          <LogOut size={16} />
          Sign Out
        </button>
      </div>
    </aside>
  )
}
