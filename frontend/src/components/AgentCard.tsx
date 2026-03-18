import { useAgentStore } from '../stores/agentStore'
import type { Agent } from '../types'

const STATUS_CONFIG = {
  idle:             { dot: 'bg-gray-500',  label: 'Nghỉ',      text: 'text-gray-400' },
  running:          { dot: 'bg-blue animate-pulse', label: 'Đang chạy', text: 'text-blue' },
  pending_approval: { dot: 'bg-violet animate-pulse', label: 'Chờ duyệt', text: 'text-violet' },
  done:             { dot: 'bg-green',     label: 'Xong',      text: 'text-green' },
  error:            { dot: 'bg-red',       label: 'Lỗi',       text: 'text-red' },
  rejected:         { dot: 'bg-red',       label: 'Bị từ chối', text: 'text-red' },
  stopped:          { dot: 'bg-gray-600',  label: 'Đã dừng',   text: 'text-gray-400' },
} as const

export default function AgentCard({ agent }: { agent: Agent }) {
  const { setSelectedAgent, setView } = useAgentStore()
  const cfg = STATUS_CONFIG[agent.status] ?? STATUS_CONFIG.idle

  const handleClick = () => {
    setSelectedAgent(agent)
    setView('agent-detail')
  }

  const handleRun = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!agent.script) return
    await fetch(`/api/agents/${agent.id}/status`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'running' }),
    })
  }

  return (
    <div
      onClick={handleClick}
      className="bg-surface border border-border rounded-lg p-3 cursor-pointer hover:border-blue/40 hover:bg-surface2 transition-all group"
    >
      <div className="flex items-start gap-3">
        <div className="text-2xl flex-shrink-0">{agent.emoji}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-white">{agent.name}</span>
            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.dot}`}/>
            <span className={`text-xs ${cfg.text}`}>{cfg.label}</span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{agent.description}</p>
          {agent.last_run && (
            <p className="text-xs text-gray-600 mt-1">
              {new Date(agent.last_run).toLocaleTimeString('vi-VN')}
            </p>
          )}
        </div>
      </div>

      {agent.script && (
        <div className="mt-2 flex gap-1.5" onClick={e => e.stopPropagation()}>
          <button
            onClick={handleRun}
            disabled={agent.status === 'running'}
            className="px-2.5 py-1 text-xs rounded bg-blue/20 text-blue border border-blue/30 hover:bg-blue/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            ▶ Run
          </button>
        </div>
      )}
    </div>
  )
}
