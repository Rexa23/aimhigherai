'use client'
import { Suspense } from 'react'
import ConversationsInner from './_inner'

export default function ConversationsPage() {
  return (
    <Suspense fallback={
      <div className="flex h-full items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
        Loading…
      </div>
    }>
      <ConversationsInner />
    </Suspense>
  )
}
