import type { Metadata } from 'next'
import '../globals.css'
import { Sidebar } from '@/components/Sidebar'
import { DashboardTopbar } from '@/components/DashboardTopbar'

export const metadata: Metadata = {
  title: 'Dashboard - AimHigherAI',
  description: 'Web3 project discovery and onboarding pipeline',
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-base)' }}>
      <Sidebar />
      <main className="flex-1 overflow-auto flex flex-col">
        {children}
      </main>
    </div>
  )
}
