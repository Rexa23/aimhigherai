'use client'
import useSWR from 'swr'
import { fetcher, agentsApi, hunterApi, AgentStatus } from '@/lib/api'
import { useState } from 'react'
import { Activity, Play, Square, Zap, TrendingUp } from 'lucide-react'
import { motion } from 'framer-motion'
import { DashboardTopbar } from '@/components/DashboardTopbar'

const AGENTS: { key: keyof AgentStatus; label: string; description: string; icon: React.FC<any> }[] = [
  {
    key: 'hunter',
    label: 'Hunter',
    description: 'Scans Twitter, Telegram, Discord & onchain sources for new leads',
    icon: Activity,
  },
  {
    key: 'outreach',
    label: 'Outreach',
    description: 'Sends personalised first messages and follow-ups via Claude API',
    icon: Zap,
  },
  {
    key: 'qualification',
    label: 'Qualification',
    description: 'Extracts hot/warm/cold signals from conversations using Claude',
    icon: TrendingUp,
  },
  {
    key: 'onboarding',
    label: 'Onboarding',
    description: 'RAG-powered step-by-step guide using AimHigherAI knowledge base',
    icon: Activity,
  },
  {
    key: 'conversion',
    label: 'Conversion',
    description: 'Sends nudges, tracks pool creation, fires urgency messages',
    icon: Zap,
  },
]

function PremiumAgentCard({
  agent,
  enabled,
  onToggle,
}: {
  agent: { key: keyof AgentStatus; label: string; description: string; icon: React.FC<any> }
  enabled: boolean
  onToggle: (key: keyof AgentStatus, val: boolean) => void
}) {
  const Icon = agent.icon

  return (
    <motion.div
      className="card-premium p-6 flex items-start justify-between gap-4"
      whileHover={{ y: -2 }}
    >
      <div className="flex items-start gap-4 flex-1">
        <div
          className="w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{
            background: enabled ? 'rgba(34, 197, 94, 0.1)' : 'rgba(99, 102, 241, 0.1)',
          }}
        >
          <Icon
            size={20}
            style={{
              color: enabled ? '#22c55e' : '#6366f1',
            }}
          />
        </div>

        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              {agent.label}
            </h3>
            <div
              className="w-2 h-2 rounded-full"
              style={{
                background: enabled ? '#22c55e' : 'var(--text-muted)',
              }}
            />
          </div>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {agent.description}
          </p>
        </div>
      </div>

      <button
        onClick={() => onToggle(agent.key, !enabled)}
        className="btn-premium flex items-center gap-2 whitespace-nowrap flex-shrink-0"
        style={{
          background: enabled ? 'var(--success)' : 'var(--bg-elevated)',
          color: enabled ? 'white' : 'var(--text-secondary)',
          border: enabled ? 'none' : '1px solid var(--border)',
        }}
      >
        {enabled ? (
          <>
            <Play size={12} />
            Running
          </>
        ) : (
          <>
            <Square size={12} />
            Stopped
          </>
        )}
      </button>
    </motion.div>
  )
}

export default function AgentsPage() {
  const { data: status, mutate: mutateStatus } = useSWR<AgentStatus>(
    '/api/v1/agents/status',
    fetcher,
    { refreshInterval: 10000 }
  )

  const { data: queueDepths } = useSWR<Record<string, number>>(
    '/api/v1/hunter/queue-depth',
    fetcher,
    { refreshInterval: 10000 }
  )

  const [triggering, setTriggering] = useState(false)

  const handleToggle = async (agent: keyof AgentStatus, enabled: boolean) => {
    try {
      const updated = await agentsApi.toggle(agent, enabled)
      mutateStatus(updated, false)
    } catch (e) {
      console.error(e)
    }
  }

  const handleTriggerHunter = async () => {
    setTriggering(true)
    try {
      await hunterApi.run()
    } catch (_) {}
    finally {
      setTriggering(false)
    }
  }

  const enabledCount = Object.values(status || {}).filter(Boolean).length

  return (
    <>
      <DashboardTopbar
        title="Agents"
        subtitle={`${enabledCount}/${AGENTS.length} agents running—autonomous Web3 GTM`}
        actions={
          <button
            onClick={handleTriggerHunter}
            disabled={triggering}
            className="btn-premium flex items-center gap-2"
          >
            {triggering ? (
              <>
                <Activity size={14} className="animate-spin" />
                Running…
              </>
            ) : (
              <>
                <Zap size={14} />
                Run Hunter
              </>
            )}
          </button>
        }
      />

      <div className="flex-1 p-6 max-w-4xl mx-auto w-full">
        <motion.div
          className="space-y-3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ staggerChildren: 0.06 }}
        >
          {AGENTS.map((agent) => (
            <motion.div key={agent.key} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
              <PremiumAgentCard
                agent={agent}
                enabled={status?.[agent.key] ?? false}
                onToggle={handleToggle}
              />
            </motion.div>
          ))}
        </motion.div>

        {queueDepths && Object.keys(queueDepths).length > 0 && (
          <motion.div className="mt-8 card-premium p-6">
            <h3 className="text-label font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
              Queue Depths
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {Object.entries(queueDepths).map(([agent, depth]) => (
                <div key={agent} className="p-4 rounded-lg" style={{ background: 'var(--bg-surface)' }}>
                  <p className="text-eyebrow mb-1">{agent}</p>
                  <p className="text-value font-bold">{depth}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </>
  )
}
