'use client'
import useSWR from 'swr'
import { analyticsApi, hunterApi, Lead, LeadList, DashboardStats } from '@/lib/api'
import { leadsApi, fetcher } from '@/lib/api'
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip, BarChart, Bar, LineChart, Line } from 'recharts'
import { TrendingUp, Users, Zap, Target, RefreshCw, ArrowUpRight, ArrowDownRight, Flame } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { DashboardTopbar } from '@/components/DashboardTopbar'

const STAGE_ORDER = ['discovered', 'contacted', 'qualified', 'onboarding', 'converted']
const STAGE_COLOR: Record<string, string> = {
  discovered: '#6366f1',
  contacted: '#8b5cf6',
  qualified: '#f59e0b',
  onboarding: '#f97316',
  converted: '#22c55e',
  disqualified: '#6b7280',
  dead: '#374151',
}

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
    },
  },
}

const item = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
}

function StatCard({
  label,
  value,
  change,
  icon: Icon,
  color,
  trend,
}: {
  label: string
  value: string | number
  change?: number
  icon: React.FC<any>
  color: string
  trend?: 'up' | 'down' | 'neutral'
}) {
  return (
    <motion.div
      variants={item}
      className="card-premium p-5 relative overflow-hidden"
      style={{
        background: `linear-gradient(135deg, rgba(99, 102, 241, 0.02), transparent)`,
      }}
    >
      <div className="flex items-start justify-between mb-4">
        <span className="text-eyebrow">{label}</span>
        <div
          className="p-2.5 rounded-lg"
          style={{
            background: `${color}20`,
          }}
        >
          <Icon size={16} style={{ color }} />
        </div>
      </div>

      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-value">{value}</div>
          {change !== undefined && (
            <div
              className="text-subtitle flex items-center gap-1 mt-2"
              style={{
                color: trend === 'up' ? '#22c55e' : trend === 'down' ? '#ef4444' : 'var(--text-muted)',
              }}
            >
              {trend === 'up' ? (
                <ArrowUpRight size={12} />
              ) : trend === 'down' ? (
                <ArrowDownRight size={12} />
              ) : null}
              {change > 0 ? '+' : ''}{change}% vs last week
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function ChartCard({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <motion.div variants={item} className="card-premium p-6">
      <h3 className="text-label font-semibold mb-6" style={{ color: 'var(--text-primary)' }}>
        {title}
      </h3>
      {children}
    </motion.div>
  )
}

function LeadRow({ lead }: { lead: Lead }) {
  const stageColors: Record<string, string> = {
    discovered: '#6366f1',
    contacted: '#8b5cf6',
    qualified: '#f59e0b',
    onboarding: '#f97316',
    converted: '#22c55e',
  }

  return (
    <Link href={`/dashboard/conversations?lead=${lead.id}`}>
      <div
        className="card-premium p-4 mb-2 cursor-pointer hover:shadow-lg transition-smooth"
      >
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              {lead.project_name}
            </div>
            <div className="text-xs mt-1 flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
              <span>{lead.chain}</span>
              {lead.token_symbol && <span>·</span>}
              {lead.token_symbol && <span>{lead.token_symbol}</span>}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                {lead.score}/100
              </div>
              <div
                className="h-1 w-20 rounded-full mt-1"
                style={{
                  background: 'var(--bg-elevated)',
                }}
              >
                <div
                  className="h-1 rounded-full transition-all"
                  style={{
                    width: `${lead.score}%`,
                    background: lead.score >= 75 ? '#22c55e' : lead.score >= 45 ? '#f59e0b' : '#6366f1',
                  }}
                />
              </div>
            </div>

            <div
              className="badge-status"
              style={{
                background:
                  lead.stage === 'converted'
                    ? 'rgba(34, 197, 94, 0.12)'
                    : lead.stage === 'onboarding'
                      ? 'rgba(249, 115, 22, 0.12)'
                      : 'rgba(99, 102, 241, 0.12)',
                color:
                  lead.stage === 'converted'
                    ? '#22c55e'
                    : lead.stage === 'onboarding'
                      ? '#f97316'
                      : '#6366f1',
              }}
            >
              {lead.stage}
            </div>
          </div>
        </div>
      </div>
    </Link>
  )
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useSWR<DashboardStats>(
    '/api/v1/analytics/dashboard',
    fetcher,
    { refreshInterval: 30000 }
  )
  const { data: leadsData } = useSWR<LeadList>('/api/v1/leads?page_size=8', fetcher, { refreshInterval: 20000 })

  const recentLeads: Lead[] = leadsData?.items ?? []

  const funnelData = STAGE_ORDER.map((s) => ({
    stage: s.charAt(0).toUpperCase() + s.slice(1),
    count: stats?.by_stage?.[s] ?? 0,
  }))

  const handleTriggerHunter = async () => {
    await hunterApi.run()
  }

  return (
    <>
      <DashboardTopbar
        title="Dashboard"
        subtitle="Real-time onboarding pipeline and metrics"
        actions={
          <button
            onClick={handleTriggerHunter}
            className="btn-premium flex items-center gap-2 text-xs"
          >
            <Zap size={13} />
            Run Hunter
          </button>
        }
      />

      <div className="flex-1 p-6 max-w-7xl mx-auto w-full">
        {/* Stats Grid */}
        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6"
        >
          <StatCard
            label="Total Leads"
            icon={Users}
            color="#6366f1"
            value={statsLoading ? '—' : stats?.total_leads ?? 0}
            change={12}
            trend="up"
          />
          <StatCard
            label="Converted"
            icon={Target}
            color="#22c55e"
            value={statsLoading ? '—' : stats?.converted_7d ?? 0}
            change={8}
            trend="up"
          />
          <StatCard
            label="This Week"
            icon={Flame}
            color="#f59e0b"
            value={statsLoading ? '—' : stats?.new_leads_7d ?? 0}
            change={-3}
            trend="down"
          />
          <StatCard
            label="Avg Score"
            icon={TrendingUp}
            color="#8b5cf6"
            value={statsLoading ? '—' : `${stats?.avg_score ?? 0}`}
            change={2}
            trend="up"
          />
        </motion.div>

        {/* Charts Grid */}
        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6"
        >
          {/* Funnel Chart */}
          <ChartCard title="Pipeline Funnel">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={funnelData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <XAxis
                  dataKey="stage"
                  stroke="var(--text-muted)"
                  style={{ fontSize: '11px' }}
                  tick={{ fill: 'var(--text-muted)' }}
                />
                <YAxis
                  stroke="var(--text-muted)"
                  style={{ fontSize: '11px' }}
                  tick={{ fill: 'var(--text-muted)' }}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                  }}
                  labelStyle={{ color: 'var(--text-primary)' }}
                />
                <Bar dataKey="count" fill="#6366f1" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* Conversion Trend */}
          <ChartCard title="Weekly Conversion">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart
                data={[
                  { week: 'Mon', conversions: 8 },
                  { week: 'Tue', conversions: 12 },
                  { week: 'Wed', conversions: 10 },
                  { week: 'Thu', conversions: 15 },
                  { week: 'Fri', conversions: 18 },
                  { week: 'Sat', conversions: 20 },
                  { week: 'Sun', conversions: 16 },
                ]}
                margin={{ top: 0, right: 0, left: -20, bottom: 0 }}
              >
                <XAxis
                  dataKey="week"
                  stroke="var(--text-muted)"
                  style={{ fontSize: '11px' }}
                  tick={{ fill: 'var(--text-muted)' }}
                />
                <YAxis
                  stroke="var(--text-muted)"
                  style={{ fontSize: '11px' }}
                  tick={{ fill: 'var(--text-muted)' }}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                  }}
                  labelStyle={{ color: 'var(--text-primary)' }}
                />
                <Line
                  type="monotone"
                  dataKey="conversions"
                  stroke="#22c55e"
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* Score Distribution */}
          <ChartCard title="Score Distribution">
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart
                data={[
                  { score: '0-20', count: 45 },
                  { score: '20-40', count: 78 },
                  { score: '40-60', count: 112 },
                  { score: '60-80', count: 234 },
                  { score: '80-100', count: 156 },
                ]}
                margin={{ top: 0, right: 0, left: -20, bottom: 0 }}
              >
                <XAxis
                  dataKey="score"
                  stroke="var(--text-muted)"
                  style={{ fontSize: '11px' }}
                  tick={{ fill: 'var(--text-muted)' }}
                />
                <YAxis
                  stroke="var(--text-muted)"
                  style={{ fontSize: '11px' }}
                  tick={{ fill: 'var(--text-muted)' }}
                />
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                  }}
                  labelStyle={{ color: 'var(--text-primary)' }}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  fill="#6366f1"
                  stroke="#8b5cf6"
                  fillOpacity={0.2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>
        </motion.div>

        {/* Recent Leads */}
        <motion.div variants={item} className="card-premium p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-label font-semibold" style={{ color: 'var(--text-primary)' }}>
              Recent Leads
            </h3>
            <Link
              href="/dashboard/pipeline"
              className="text-xs font-medium"
              style={{ color: 'var(--accent)' }}
            >
              View all →
            </Link>
          </div>

          <div className="space-y-2">
            {recentLeads.length > 0 ? (
              recentLeads.map((lead) => <LeadRow key={lead.id} lead={lead} />)
            ) : (
              <div
                className="py-8 text-center"
                style={{ color: 'var(--text-muted)' }}
              >
                No leads yet. Run Hunter to discover projects.
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </>
  )
}
