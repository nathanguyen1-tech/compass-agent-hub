export type AgentStatus = 'idle' | 'running' | 'pending_approval' | 'done' | 'error' | 'rejected' | 'stopped'

export interface AgentSession {
  key: string
  channel: string
  updated_at_ms: number
  updated_ago: string
  is_active: boolean
  msg_count: number
  age_sec: number
}

export interface Agent {
  id: string
  name: string
  emoji: string
  description: string
  script: string
  requires_approval: boolean
  status: AgentStatus
  last_run: string | null
  last_log: string | null
  openclaw_agent_id: string
  // v3
  model: string
  source: 'manual' | 'openclaw'
  a2a_enabled: boolean
  workspace_path: string
  active_sessions?: number
  total_sessions?: number
  sessions?: AgentSession[]
  messages_today?: { sent: number; received: number; total: number }
}

export interface Binding {
  agent_id: string
  channel: string
  account_id: string
  peer_kind: string
  peer_id: string
  source: string
}

export interface Topology {
  agents: Agent[]
  bindings: Binding[]
  accounts: Record<string, string[]>
  a2a_enabled: boolean
}

export interface A2AMessage {
  id: number
  from: string
  to: string
  preview: string
  ts: string
}

export interface ActivityEvent {
  id: number
  agent_id: string
  message: string
  level: 'info' | 'success' | 'error' | 'warning' | 'progress'
  ts: string
}

export interface Approval {
  id: string
  agent_id: string
  status: string
  created_at: string
  resolved_at: string | null
}
