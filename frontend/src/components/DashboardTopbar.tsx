'use client'
import React from 'react'
import { Search, Bell, Settings } from 'lucide-react'

interface DashboardTopbarProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}

export function DashboardTopbar({ title, subtitle, actions }: DashboardTopbarProps) {
  return (
    <div
      className="flex items-center justify-between px-6 py-4 border-b"
      style={{
        background: 'var(--bg-base)',
        borderColor: 'var(--border)',
      }}
    >
      <div className="flex-1">
        <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
          {title}
        </h1>
        {subtitle && (
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {subtitle}
          </p>
        )}
      </div>

      <div className="flex items-center gap-3 ml-6">
        {/* Search */}
        <div
          className="hidden md:flex items-center gap-2 px-3 py-2 rounded-lg"
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
          }}
        >
          <Search size={14} style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search…"
            className="bg-transparent text-xs w-32 outline-none"
            style={{ color: 'var(--text-primary)' }}
          />
        </div>

        {/* Notifications */}
        <button
          className="p-2 rounded-lg transition-smooth hover:bg-elevated"
          style={{
            background: 'transparent',
          }}
        >
          <Bell size={16} style={{ color: 'var(--text-secondary)' }} />
        </button>

        {/* Settings */}
        <button
          className="p-2 rounded-lg transition-smooth hover:bg-elevated"
          style={{
            background: 'transparent',
          }}
        >
          <Settings size={16} style={{ color: 'var(--text-secondary)' }} />
        </button>

        {/* Custom actions */}
        {actions}
      </div>
    </div>
  )
}
