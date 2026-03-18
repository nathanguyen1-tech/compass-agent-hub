import { create } from 'zustand'
import type { Agent, ActivityEvent, Approval } from '../types'

interface AgentStore {
  agents: Agent[]
  events: ActivityEvent[]
  approvals: Approval[]
  connected: boolean
  view: 'command-center' | 'general' | 'agent-detail'
  selectedAgent: Agent | null

  setAgents: (a: Agent[]) => void
  addEvent: (e: ActivityEvent) => void
  setApprovals: (a: Approval[]) => void
  setConnected: (v: boolean) => void
  setView: (v: AgentStore['view']) => void
  setSelectedAgent: (a: Agent | null) => void
  updateAgentStatus: (id: string, status: Agent['status']) => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  agents:        [],
  events:        [],
  approvals:     [],
  connected:     false,
  view:          'command-center',
  selectedAgent: null,

  setAgents:         (agents)  => set({ agents }),
  addEvent:          (event)   => set((s) => ({ events: [...s.events.slice(-199), event] })),
  setApprovals:      (a)       => set({ approvals: a }),
  setConnected:      (v)       => set({ connected: v }),
  setView:           (view)    => set({ view }),
  setSelectedAgent:  (a)       => set({ selectedAgent: a }),
  updateAgentStatus: (id, status) =>
    set((s) => ({ agents: s.agents.map((a) => a.id === id ? { ...a, status } : a) })),
}))
