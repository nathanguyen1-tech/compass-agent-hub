import { create } from 'zustand'
import type { Agent, ActivityEvent, Approval, Topology, A2AMessage } from '../types'

type View = 'command-center' | 'general' | 'agent-detail' | 'topology' | 'message-bus'

interface AgentStore {
  agents: Agent[]
  events: ActivityEvent[]
  approvals: Approval[]
  topology: Topology | null
  a2aMessages: A2AMessage[]
  connected: boolean
  view: View
  selectedAgent: Agent | null

  setAgents: (a: Agent[]) => void
  addEvent: (e: ActivityEvent) => void
  setApprovals: (a: Approval[]) => void
  setTopology: (t: Topology) => void
  addA2AMessage: (m: A2AMessage) => void
  setConnected: (v: boolean) => void
  setView: (v: View) => void
  setSelectedAgent: (a: Agent | null) => void
  updateAgentStatus: (id: string, status: Agent['status']) => void
}

export const useAgentStore = create<AgentStore>((set) => ({
  agents:      [],
  events:      [],
  approvals:   [],
  topology:    null,
  a2aMessages: [],
  connected:   false,
  view:        'command-center',
  selectedAgent: null,

  setAgents:    (agents)   => set({ agents }),
  addEvent:     (event)    => set((s) => ({ events: [...s.events.slice(-299), event] })),
  setApprovals: (a)        => set({ approvals: a }),
  setTopology:  (t)        => set({ topology: t }),
  addA2AMessage:(m)        => set((s) => ({ a2aMessages: [...s.a2aMessages.slice(-99), m] })),
  setConnected: (v)        => set({ connected: v }),
  setView:      (view)     => set({ view }),
  setSelectedAgent: (a)   => set({ selectedAgent: a }),
  updateAgentStatus: (id, status) =>
    set((s) => ({ agents: s.agents.map((a) => a.id === id ? { ...a, status } : a) })),
}))
