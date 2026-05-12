'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import useSWR from 'swr'
import { fetcher, outreachApi, suggestionsApi, Lead, LeadList, Conversation, Message } from '@/lib/api'
import { Send, Sparkles, Loader2, MessageCircle, Zap } from 'lucide-react'
import { format } from 'date-fns'
import { clsx } from 'clsx'
import { motion } from 'framer-motion'

const PRIORITY_DOT: Record<string, string> = {
  hot: '#ef4444',
  warm: '#f59e0b',
  cold: '#818cf8',
}

function PremiumLeadListItem({
  lead,
  selected,
  onClick,
}: {
  lead: Lead
  selected: boolean
  onClick: () => void
}) {
  return (
    <motion.button
      onClick={onClick}
      className="w-full text-left px-4 py-3.5 transition-smooth border-b group"
      style={{
        borderColor: 'var(--border)',
        borderLeft: selected ? '3px solid var(--accent)' : '3px solid transparent',
        background: selected ? 'var(--bg-elevated)' : 'transparent',
      }}
      whileHover={{ backgroundColor: 'var(--bg-hover)' }}
    >
      <div className="flex items-center gap-2.5 mb-1.5">
        <div
          className="w-2.5 h-2.5 rounded-full flex-shrink-0"
          style={{ background: PRIORITY_DOT[lead.priority] }}
        />
        <span
          className="text-xs font-semibold truncate group-hover:text-accent transition-colors"
          style={{ color: selected ? 'var(--accent)' : 'var(--text-primary)' }}
        >
          {lead.project_name}
        </span>
      </div>
      <div className="text-xs pl-4 truncate space-x-1" style={{ color: 'var(--text-muted)' }}>
        <span className="capitalize">{lead.stage}</span>
        <span>·</span>
        <span>{lead.chain}</span>
        {lead.score >= 75 && (
          <>
            <span>·</span>
            <span className="font-medium" style={{ color: '#22c55e' }}>
              ✓
            </span>
          </>
        )}
      </div>
    </motion.button>
  )
}

function ChatMessage({ msg }: { msg: Message }) {
  const isOut = msg.direction === 'outbound'
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={clsx('flex mb-4', isOut ? 'justify-end' : 'justify-start')}
    >
      <div style={{ maxWidth: '78%' }}>
        <div
          className="px-4 py-3 text-sm leading-relaxed rounded-lg"
          style={{
            background: isOut ? 'var(--accent)' : 'var(--bg-elevated)',
            color: isOut ? 'white' : 'var(--text-primary)',
            border: isOut ? 'none' : '1px solid var(--border)',
          }}
        >
          {msg.content}
        </div>
        <div
          className={clsx('text-xs mt-1.5 flex items-center gap-1.5', isOut ? 'justify-end' : 'justify-start')}
          style={{ color: 'var(--text-muted)' }}
        >
          {isOut && msg.ai_generated && (
            <>
              <Sparkles size={11} style={{ color: 'var(--accent)' }} />
              <span>AI Generated</span>
            </>
          )}
          <span>{format(new Date(msg.created_at), 'HH:mm')}</span>
        </div>
      </div>
    </motion.div>
  )
}

function AISuggestionCard({ text, index, onClick }: { text: string; index: number; onClick: () => void }) {
  return (
    <motion.button
      onClick={onClick}
      className="w-full text-left p-4 rounded-lg transition-smooth card-premium group"
      whileHover={{ y: -1 }}
    >
      <div
        className="flex items-center gap-2 mb-2 text-xs font-semibold"
        style={{ color: 'var(--accent)' }}
      >
        <Sparkles size={12} />
        <span>Option {index + 1}</span>
      </div>
      <p className="text-xs leading-relaxed group-hover:text-accent transition-colors" style={{ color: 'var(--text-secondary)' }}>
        {text}
      </p>
    </motion.button>
  )
}

export default function ConversationsInner() {
  const searchParams = useSearchParams()
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(searchParams.get('lead'))
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [loadingSuggs, setLoadingSuggs] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data: leadsData } = useSWR<LeadList>('/api/v1/leads?page_size=100', fetcher, { refreshInterval: 20000 })
  const leads: Lead[] = leadsData?.items ?? []
  const selectedLead = leads.find((l) => l.id === selectedLeadId)

  const { data: convData, mutate: mutateConvs } = useSWR<Conversation[]>(
    selectedLeadId ? `/api/v1/leads/${selectedLeadId}/conversations` : null,
    fetcher,
    { refreshInterval: 8000 }
  )
  const conversations: Conversation[] = convData ?? []
  const activeConv = conversations.find((c) => c.is_active) ?? conversations[0]
  const messages: Message[] = activeConv?.messages ?? []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  const handleSend = async () => {
    if (!input.trim() || !selectedLeadId || !activeConv || sending) return
    setSending(true)
    try {
      await outreachApi.send(selectedLeadId, activeConv.channel, input)
      setInput('')
      setSuggestions([])
      setTimeout(() => mutateConvs(), 1500)
    } finally {
      setSending(false)
    }
  }

  const loadSuggestions = useCallback(async () => {
    if (!selectedLeadId || !activeConv || !messages.length) return
    const lastInbound = [...messages].reverse().find((m) => m.direction === 'inbound')
    if (!lastInbound) return
    setLoadingSuggs(true)
    try {
      const res = await suggestionsApi.get(selectedLeadId, activeConv.id, lastInbound.content)
      setSuggestions(res.suggestions ?? [])
    } finally {
      setLoadingSuggs(false)
    }
  }, [selectedLeadId, activeConv, messages])

  return (
    <div className="h-full flex" style={{ minHeight: 0 }}>
      {/* Left Sidebar - Lead List */}
      <motion.div
        className="w-64 shrink-0 border-r flex flex-col"
        style={{
          borderColor: 'var(--border)',
          background: 'linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-base) 100%)',
        }}
      >
        <div className="px-5 py-4 border-b shrink-0" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2">
            <MessageCircle size={14} style={{ color: 'var(--accent)' }} />
            <span className="text-eyebrow">Projects</span>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {leads.length === 0 ? (
            <div
              className="flex flex-col items-center justify-center h-32 text-center"
              style={{ color: 'var(--text-muted)' }}
            >
              <MessageCircle size={24} className="mb-2 opacity-40" />
              <p className="text-xs font-medium">No projects</p>
            </div>
          ) : (
            leads.map((lead) => (
              <PremiumLeadListItem
                key={lead.id}
                lead={lead}
                selected={lead.id === selectedLeadId}
                onClick={() => {
                  setSelectedLeadId(lead.id)
                  setSuggestions([])
                }}
              />
            ))
          )}
        </div>
      </motion.div>

      {/* Center - Chat Area */}
      <motion.div className="flex-1 flex flex-col min-h-0">
        {selectedLead ? (
          <>
            {/* Chat Header */}
            <div
              className="px-6 py-4 border-b flex items-center justify-between shrink-0"
              style={{
                borderColor: 'var(--border)',
                background: 'var(--bg-base)',
              }}
            >
              <div>
                <h2
                  className="text-sm font-semibold"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {selectedLead.project_name}
                </h2>
                <div className="text-xs mt-1 flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
                  <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded" style={{ background: 'var(--bg-surface)' }}>
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: PRIORITY_DOT[selectedLead.priority] }} />
                    <span className="capitalize">{selectedLead.stage}</span>
                  </span>
                  <span>{activeConv?.channel ?? '—'}</span>
                </div>
              </div>
              <button
                onClick={loadSuggestions}
                disabled={loadingSuggs}
                className="btn-premium-ghost flex items-center gap-2 text-xs"
              >
                {loadingSuggs ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Sparkles size={12} />
                )}
                Suggestions
              </button>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto px-6 py-5">
              {messages.length === 0 ? (
                <div
                  className="flex flex-col items-center justify-center h-full text-center"
                  style={{ color: 'var(--text-muted)' }}
                >
                  <MessageCircle size={32} className="mb-2 opacity-30" />
                  <p className="text-sm font-medium">No messages yet</p>
                  <p className="text-xs mt-1">Start the conversation</p>
                </div>
              ) : (
                messages.map((msg) => <ChatMessage key={msg.id} msg={msg} />)
              )}
              <div ref={bottomRef} />
            </div>

            {/* Message Input */}
            <div className="px-6 py-4 border-t shrink-0" style={{ borderColor: 'var(--border)', background: 'var(--bg-base)' }}>
              <div className="flex gap-3">
                <input
                  className="input flex-1 text-sm"
                  placeholder="Type a message…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
                />
                <button
                  onClick={handleSend}
                  disabled={sending || !input.trim()}
                  className="btn-premium flex items-center gap-2 whitespace-nowrap"
                >
                  {sending ? (
                    <>
                      <Loader2 size={14} className="animate-spin" />
                      Sending…
                    </>
                  ) : (
                    <>
                      <Send size={14} />
                      Send
                    </>
                  )}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div
            className="flex-1 flex flex-col items-center justify-center"
            style={{ color: 'var(--text-muted)' }}
          >
            <MessageCircle size={40} className="mb-3 opacity-30" />
            <p className="text-sm font-medium">Select a project to start messaging</p>
          </div>
        )}
      </motion.div>

      {/* Right Sidebar - AI Suggestions Panel */}
      <motion.div
        className="w-72 shrink-0 border-l flex flex-col"
        style={{
          borderColor: 'var(--border)',
          background: 'linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-base) 100%)',
        }}
      >
        <div className="px-5 py-4 border-b shrink-0" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-2">
            <Sparkles size={14} style={{ color: 'var(--accent)' }} />
            <span className="text-eyebrow">AI Suggestions</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {suggestions.length === 0 ? (
            <div
              className="flex flex-col items-center justify-center h-32 text-center p-3"
              style={{ color: 'var(--text-muted)' }}
            >
              <Sparkles size={24} className="mb-2 opacity-20" />
              <p className="text-xs font-medium">Click "Suggestions" to generate AI reply options</p>
            </div>
          ) : (
            suggestions.map((s, i) => (
              <AISuggestionCard
                key={i}
                text={s}
                index={i}
                onClick={() => setInput(s)}
              />
            ))
          )}
        </div>

        {/* Lead Stats Footer */}
        {selectedLead && (
          <motion.div
            className="px-4 py-4 border-t shrink-0 space-y-3"
            style={{ borderColor: 'var(--border)' }}
          >
            <div>
              <p className="text-eyebrow mb-2">Lead Details</p>
              <div className="space-y-2">
                <div className="flex items-center justify-between px-3 py-2 rounded-lg" style={{ background: 'var(--bg-surface)' }}>
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    Quality Score
                  </span>
                  <span
                    className="text-xs font-bold"
                    style={{
                      color: selectedLead.score >= 75 ? '#22c55e' : selectedLead.score >= 45 ? '#f59e0b' : '#6366f1',
                    }}
                  >
                    {selectedLead.score}/100
                  </span>
                </div>
                <div className="flex items-center justify-between px-3 py-2 rounded-lg" style={{ background: 'var(--bg-surface)' }}>
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    Market Cap
                  </span>
                  <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                    {selectedLead.market_cap_usd ? `$${(selectedLead.market_cap_usd / 1000000).toFixed(1)}M` : '—'}
                  </span>
                </div>
                <div className="flex items-center justify-between px-3 py-2 rounded-lg" style={{ background: 'var(--bg-surface)' }}>
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    Onboarding
                  </span>
                  <span className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Step {selectedLead.onboarding_step}
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </motion.div>
    </div>
  )
}
