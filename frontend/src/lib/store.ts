import { create } from 'zustand'
import { Lead, AgentStatus, DashboardStats } from './api'

interface WsEvent {
  event: string
  lead_id: string
  project_name: string
  timestamp: string
}

interface AppState {
  // Leads
  leads: Lead[]
  selectedLeadId: string | null
  setLeads: (leads: Lead[]) => void
  upsertLead: (lead: Lead) => void
  selectLead: (id: string | null) => void

  // Dashboard stats
  stats: DashboardStats | null
  setStats: (s: DashboardStats) => void

  // Agent status
  agentStatus: AgentStatus | null
  setAgentStatus: (s: AgentStatus) => void

  // WebSocket
  wsConnected: boolean
  recentEvents: WsEvent[]
  wsConnect: () => void
  wsDisconnect: () => void

  // UI state
  sidebarOpen: boolean
  setSidebarOpen: (v: boolean) => void
  activeView: 'dashboard' | 'pipeline' | 'conversations' | 'agents' | 'knowledge'
  setActiveView: (v: AppState['activeView']) => void
}

const WS_URL = (process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000') + '/ws'
let socket: WebSocket | null = null

export const useAppStore = create<AppState>((set, get) => ({
  leads: [],
  selectedLeadId: null,
  setLeads: (leads) => set({ leads }),
  upsertLead: (lead) =>
    set((s) => ({
      leads: s.leads.some((l) => l.id === lead.id)
        ? s.leads.map((l) => (l.id === lead.id ? lead : l))
        : [lead, ...s.leads],
    })),
  selectLead: (id) => set({ selectedLeadId: id }),

  stats: null,
  setStats: (stats) => set({ stats }),

  agentStatus: null,
  setAgentStatus: (agentStatus) => set({ agentStatus }),

  wsConnected: false,
  recentEvents: [],

  wsConnect: () => {
    if (socket) return
    socket = new WebSocket(WS_URL)

    socket.onopen = () => set({ wsConnected: true })

    socket.onmessage = (e) => {
      try {
        const data: WsEvent = JSON.parse(e.data)
        set((s) => ({
          recentEvents: [data, ...s.recentEvents.slice(0, 49)],
        }))
        // If conversion event, refresh stats
        if (data.event === 'conversion') {
          // SWR will handle refetch via mutate — just trigger a notification
        }
      } catch (_) {}
    }

    socket.onclose = () => {
      set({ wsConnected: false })
      socket = null
      // Auto-reconnect after 3s
      setTimeout(() => get().wsConnect(), 3000)
    }

    socket.onerror = () => {
      socket?.close()
    }
  },

  wsDisconnect: () => {
    socket?.close()
    socket = null
    set({ wsConnected: false })
  },

  sidebarOpen: true,
  setSidebarOpen: (v) => set({ sidebarOpen: v }),

  activeView: 'dashboard',
  setActiveView: (v) => set({ activeView: v }),
}))
