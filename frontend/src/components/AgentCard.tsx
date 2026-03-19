import { Play, ChevronRight, Loader2 } from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'
import type { Agent } from '../types'

const STATUS_CONFIG = {
  idle:             { dot: 'bg-gray-600',              label: 'Nghỉ',       text: 'text-gray-500' },
  running:          { dot: 'bg-blue animate-pulse',    label: 'Đang chạy',  text: 'text-blue' },
  pending_approval: { dot: 'bg-violet animate-pulse',  label: 'Chờ duyệt', text: 'text-violet' },
  done:             { dot: 'bg-green',                 label: 'Xong',       text: 'text-green' },
  error:            { dot: 'bg-red',                   label: 'Lỗi',        text: 'text-red' },
  rejected:         { dot: 'bg-red',                   label: 'Từ chối',    text: 'text-red' },
  stopped:          { dot: 'bg-gray-700',              label: 'Đã dừng',   text: 'text-gray-500' },
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
    <div onClick={handleClick}
      className="group flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer hover:bg-white/5 transition-colors border border-transparent hover:border-border">
      {/* Emoji avatar */}
      <div className="w-8 h-8 rounded-lg bg-surface2 flex items-center justify-center text-lg shrink-0 group-hover:scale-105 transition-transform">
        {agent.emoji}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-gray-200 truncate">{agent.name}</span>
          {agent.status === 'running' && <Loader2 size={10} className="text-blue animate-spin shrink-0"/>}
        </div>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${cfg.dot}`}/>
          <span className={`text-[11px] ${cfg.text}`}>{cfg.label}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        {agent.script && (
          <button onClick={handleRun} disabled={agent.status === 'running'}
            className="w-6 h-6 flex items-center justify-center rounded bg-blue/20 text-blue hover:bg-blue/30 disabled:opacity-40 transition-colors"
            title="Chạy ngay">
            <Play size={10} fill="currentColor"/>
          </button>
        )}
        <ChevronRight size={13} className="text-gray-600"/>
      </div>
    </div>
  )
}
