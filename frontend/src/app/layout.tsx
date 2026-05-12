import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AimHigher AI',
  description: 'Autonomous onboarding agents for Web3 growth.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ background: 'var(--bg-base)' }}>{children}</body>
    </html>
  )
}
