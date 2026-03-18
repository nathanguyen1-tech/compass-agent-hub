export type AgentStatus = 'idle' | 'running' | 'pending_approval' | 'done' | 'error' | 'rejected' | 'stopped'

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
