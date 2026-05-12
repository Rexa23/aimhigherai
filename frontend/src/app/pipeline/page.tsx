'use client'
import useSWR from 'swr'
import { fetcher, leadsApi, Lead, LeadList, Stage } from '@/lib/api'
import { useState } from 'react'
import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'
import { Filter, Zap, TrendingUp } from 'lucide-react'
import { motion } from 'framer-motion'
import { DashboardTopbar } from '@/components/DashboardTopbar'

const STAGES: { key: Stage; label: string; color: string; description: string }[] = [
  { key: 'discovered', label: 'Discovered', color: '#6366f1', description: 'New projects' },
  { key: 'contacted', label: 'Contacted', color: '#8b5cf6', description: 'Initial outreach' },
  { key: 'qualified', label: 'Qualified', color: '#f59e0b', description: 'Fit confirmed' },
  { key: 'onboarding', label: 'Onboarding', color: '#f97316', description: 'In progress' },
  { key: 'converted', label: 'Converted', color: '#22c55e', description: 'Success' },
]

function ScoreBar({ score }: { score: number }) {
  const color = score >= 75 ? '#22c55e' : score >= 45 ? '#f59e0b' : '#6366f1'
  return (
    <div className="h-1.5 rounded-full w-full" style={{ background: 'var(--bg-elevated)' }}>
      <motion.div
        className="h-1.5 rounded-full"
        initial={{ width: 0 }}
        animate={{ width: `${score}%` }}
        transition={{ duration: 0.4 }}
        style={{ background: color }}
      />
    </div>
  )
}

function PremiumLeadCard({ lead }: { lead: Lead }) {
  const priorityColors: Record<string, { bg: string; text: string }> = {
    hot: { bg: 'rgba(239,68,68,0.12)', text: '#ef4444' },
    warm: { bg: 'rgba(245,158,11,0.12)', text: '#f59e0b' },
    cold: { bg: 'rgba(99,102,241,0.12)', text: '#818cf8' },
  }

  const colors = priorityColors[lead.priority] || priorityColors.cold

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.2 }}
      whileHover={{ y: -2 }}
    >
      <Link href={`/dashboard/conversations?lead=${lead.id}`}>
        <div
          className="card-premium p-4 mb-3 cursor-pointer group"
          style={{
            border: `1px solid var(--border)`,
          }}
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-2 mb-3">
            <div className="flex-1 min-w-0">
              <h4
                className="text-sm font-semibold truncate group-hover:text-accent transition-colors"
                style={{ color: 'var(--text-primary)' }}
              >
                {lead.project_name}
              </h4>
              <p
                className="text-xs mt-1"
                style={{ color: 'var(--text-muted)' }}
              >
                {lead.chain}
                {lead.token_symbol && ` · ${lead.token_symbol}`}
              </p>
            </div>

            <div
              className="badge-status flex-shrink-0"
              style={{
                background: colors.bg,
                color: colors.text,
              }}
            >
              {lead.priority}
            </div>
          </div>

          {/* Market Cap */}
          {lead.market_cap_usd && (
            <div
              className="text-xs mb-3 font-medium"
              style={{ color: 'var(--text-secondary)' }}
            >
              ${(lead.market_cap_usd / 1000000).toFixed(1)}M cap
            </div>
          )}

          {/* Pain Signals */}
          {lead.pain_signals.length > 0 && (
            <div
              className="text-xs px-2.5 py-1.5 rounded-md mb-3 flex items-center gap-1.5 truncate"
              style={{
                background: 'rgba(239,68,68,0.08)',
                color: '#fc8181',
              }}
            >
              <Zap size={12} className="flex-shrink-0" />
              <span className="truncate">{lead.pain_signals[0]}</span>
            </div>
          )}

          {/* Score Bar */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                Quality Score
              </span>
              <span className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>
                {lead.score}/100
              </span>
            </div>
            <ScoreBar score={lead.score} />
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
            <span
              className="text-xs"
              style={{ color: 'var(--text-muted)' }}
            >
              {lead.source_platform}
            </span>
            <span
              className="text-xs"
              style={{ color: 'var(--text-muted)' }}
            >
              {formatDistanceToNow(new Date(lead.updated_at), { addSuffix: true })}
            </span>
          </div>
        </div>
      </Link>
    </motion.div>
  )
}

function KanbanColumn({
  stage,
  label,
  color,
  description,
  leads,
}: {
  stage: Stage
  label: string
  color: string
  description: string
  leads: Lead[]
}) {
  return (
    <motion.div
      className="flex flex-col flex-shrink-0"
      style={{ width: 320, minHeight: '100%' }}
      layout
    >
      {/* Column Header */}
      <motion.div
        className="px-4 py-3 rounded-lg mb-4 border"
        style={{
          background: `${color}08`,
          borderColor: `${color}30`,
        }}
      >
        <div className="flex items-center gap-2 mb-2">
          <div
            className="w-2.5 h-2.5 rounded-full"
            style={{ background: color }}
          />
          <h3
            className="text-sm font-semibold"
            style={{ color }}
          >
            {label}
          </h3>
        </div>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {description}
        </p>
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>
            {leads.length} {leads.length === 1 ? 'lead' : 'leads'}
          </span>
          {leads.some((l) => l.priority === 'hot') && (
            <div
              className="flex items-center gap-1 badge-status"
              style={{
                background: 'rgba(239,68,68,0.12)',
                color: '#ef4444',
              }}
            >
              <Zap size={10} />
              Hot
            </div>
          )}
        </div>
      </motion.div>

      {/* Cards Container */}
      <div className="flex-1 overflow-y-auto pr-2 space-y-2">
        {leads.length === 0 ? (
          <div
            className="flex flex-col items-center justify-center py-12 text-center"
            style={{ color: 'var(--text-muted)' }}
          >
            <div className="w-10 h-10 rounded-lg mb-2 flex items-center justify-center" style={{ background: 'var(--bg-elevated)' }}>
              <TrendingUp size={16} />
            </div>
            <p className="text-xs font-medium">No leads yet</p>
            <p className="text-xs mt-1">Leads will appear here as they move through the pipeline</p>
          </div>
        ) : (
          leads.map((lead) => (
            <PremiumLeadCard key={lead.id} lead={lead} />
          ))
        )}
      </div>
    </motion.div>
  )
}

export default function PipelinePage() {
  const [chain, setChain] = useState<string>('')
  const [priority, setPriority] = useState<string>('')

  const params: Record<string, string> = { page_size: '200' }
  if (chain) params.chain = chain
  if (priority) params.priority = priority

  const qs = new URLSearchParams(params).toString()
  const { data } = useSWR<LeadList>(`/api/v1/leads?${qs}`, fetcher, { refreshInterval: 15000 })
  const leads: Lead[] = data?.items ?? []

  const byStage = (stage: Stage) => leads.filter((l) => l.stage === stage)
  const totalLeads = leads.length

  return (
    <>
      <DashboardTopbar
        title="Pipeline"
        subtitle={`Real-time kanban view of ${totalLeads} leads across all stages`}
      />

      <div className="flex-1 flex flex-col bg-base overflow-hidden">
        {/* Toolbar */}
        <div
          className="flex items-center gap-3 px-6 py-3 border-b shrink- flex-wrap md:flex-nowrap"
          style={{ borderColor: 'var(--border)' }}
        >
          <div className="flex items-center gap-2">
            <Filter size={14} style={{ color: 'var(--text-muted)' }} />
            <span className="text-xs text-secondary font-medium">Filter:</span>
          </div>

          <select
            className="input text-xs py-1.5 bg-surface"
            style={{ width: 'auto', minWidth: 120 }}
            value={chain}
            onChange={(e) => setChain(e.target.value)}
          >
            <option value="">All chains</option>
            {['ethereum', 'bnb', 'solana', 'base'].map((c) => (
              <option key={c} value={c}>
                {c.charAt(0).toUpperCase() + c.slice(1)}
              </option>
            ))}
          </select>

          <select
            className="input text-xs py-1.5 bg-surface"
            style={{ width: 'auto', minWidth: 120 }}
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
          >
            <option value="">All priorities</option>
            {['hot', 'warm', 'cold'].map((p) => (
              <option key={p} value={p}>
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>

          <div className="ml-auto text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
            {totalLeads} total
          </div>
        </div>

        {/* Kanban Board */}
        <motion.div
          className="flex-1 overflow-x-auto"
          layout
        >
          <motion.div
            className="flex gap-4 p-6 h-full min-w-max"
            layout
          >
            {STAGES.map(({ key, label, color, description }) => (
              <KanbanColumn
                key={key}
                stage={key}
                label={label}
                color={color}
                description={description}
                leads={byStage(key)}
              />
            ))}
          </motion.div>
        </motion.div>
      </div>
    </>
  )
}
