'use client'
import Link from 'next/link'
import Image from 'next/image'
import { usePathname } from 'next/navigation'
import { useEffect } from 'react'
import {
  LayoutDashboard, Kanban, MessageSquare,
  Bot, BookOpen, Wifi, WifiOff, ChevronRight
} from 'lucide-react'
import { useAppStore } from '@/lib/store'
import { clsx } from 'clsx'

const NAV = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/dashboard/pipeline', icon: Kanban, label: 'Pipeline' },
  { href: '/dashboard/conversations', icon: MessageSquare, label: 'Conversations' },
  { href: '/dashboard/agents', icon: Bot, label: 'Agents' },
  { href: '/dashboard/knowledge', icon: BookOpen, label: 'Knowledge' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { wsConnect, wsConnected, recentEvents } = useAppStore()

  useEffect(() => { wsConnect() }, [wsConnect])

  const lastEvent = recentEvents[0]

  return (
    <aside
      className="flex flex-col w-56 shrink-0 border-r transition-smooth"
      style={{
        background: 'linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-base) 100%)',
        borderColor: 'var(--border)',
      }}
    >
      {/* Logo & Branding */}
      <div className="px-5 py-6 border-b" style={{ borderColor: 'var(--border)' }}>
        <Link href="/dashboard" className="flex items-center justify-start hover:opacity-90 transition-opacity" aria-label="AimHigherAI Dashboard">
          <Image
            src="/logo.png"
            alt="AimHigherAI Logo"
            width={140}
            height={40}
            priority
            className="object-contain"
          />
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-5 flex flex-col gap-1">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = pathname === href
          return (
            <Link
              key={href}
              href={href}
              className="group relative flex items-center gap-3 px-3 py-2.5 rounded-9 text-sm font-medium transition-smooth"
              style={{
                background: active ? 'var(--accent)' : 'transparent',
                color: active ? 'white' : 'var(--text-secondary)',
              }}
            >
              {/* Active indicator */}
              {active && (
                <div
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 rounded-r"
                  style={{
                    background: 'rgba(255, 255, 255, 0.4)',
                  }}
                />
              )}
              <Icon size={16} strokeWidth={1.5} className="flex-shrink-0" />
              <span>{label}</span>
              {active && <ChevronRight size={14} className="ml-auto opacity-60" />}
            </Link>
          )
        })}
      </nav>

      {/* Status & Events */}
      <div className="px-4 py-4 border-t space-y-3" style={{ borderColor: 'var(--border)' }}>
        {/* Connection status */}
        <div
          className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium"
          style={{
            background: wsConnected ? 'rgba(34, 197, 94, 0.08)' : 'rgba(239, 68, 68, 0.08)',
            color: wsConnected ? '#22c55e' : '#ef4444',
          }}
        >
          <div
            className="w-1.5 h-1.5 rounded-full status-pulse"
            style={{
              background: wsConnected ? '#22c55e' : '#ef4444',
            }}
          />
          <span>{wsConnected ? 'Live' : 'Reconnecting…'}</span>
        </div>

        {/* Last event */}
        {lastEvent && (
          <div className="card-premium p-3">
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Last Activity
            </div>
            <div
              className="text-xs font-medium mt-1.5 truncate"
              style={{ color: 'var(--text-primary)' }}
            >
              {lastEvent.event === 'conversion' ? (
                <span style={{ color: 'var(--success)' }}>
                  🎉 {lastEvent.project_name}
                </span>
              ) : (
                <span>{lastEvent.project_name}</span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t text-xs" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
        <div className="flex items-center justify-center">
          <Image
            src="/logo.png"
            alt="AimHigherAI Logo"
            width={140}
            height={40}
            priority
            className="object-contain"
          />
        </div>
      </div>
    </aside>
  )
}
