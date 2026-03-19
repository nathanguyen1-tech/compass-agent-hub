import { ChevronLeft, Play, Terminal, Clock, Hash, Bot } from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'
import ActivityStream from '../components/ActivityStream'

export default function AgentDetail() {
  const { selectedAgent, setView, setSelectedAgent } = useAgentStore()

  if (!selectedAgent) { setView('command-center'); return null }

  const handleRun = async () => {
    if (!selectedAgent.script) return
    await fetch(`/api/agents/${selectedAgent.id}/status`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'running' }),
    })
  }

  const fields = [
    { Icon: Hash,     label: 'ID',            value: selectedAgent.id },
    { Icon: Bot,      label: 'OpenClaw ID',    value: selectedAgent.openclaw_agent_id || '—' },
    { Icon: Terminal, label: 'Script',         value: selectedAgent.script || '—' },
    { Icon: Clock,    label: 'Lần chạy cuối', value: selectedAgent.last_run ? new Date(selectedAgent.last_run).toLocaleString('vi-VN') : '—' },
  ]

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-surface shrink-0">
        <button onClick={() => { setSelectedAgent(null); setView('command-center') }}
          className="flex items-center gap-1 text-xs text-gray-500 hover:text-white transition-colors">
          <ChevronLeft size={13}/> Bản Chỉ Huy
        </button>
        <span className="text-gray-700">/</span>
        <span className="text-sm font-semibold text-white flex items-center gap-1.5">
          <span>{selectedAgent.emoji}</span>{selectedAgent.name}
        </span>

        {/* Status badge */}
        <span className={`ml-2 text-[10px] font-bold px-2 py-0.5 rounded-full border ${
          selectedAgent.status === 'running'
            ? 'text-blue border-blue/30 bg-blue/10'
            : selectedAgent.status === 'error'
            ? 'text-red border-red/30 bg-red/10'
            : 'text-gray-500 border-gray-700 bg-white/5'
        }`}>
          {selectedAgent.status.toUpperCase()}
        </span>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left panel */}
        <div className="w-64 shrink-0 border-r border-border p-4 overflow-y-auto space-y-5">
          {/* Avatar */}
          <div className="flex items-center gap-3">
            <div className="w-14 h-14 rounded-2xl bg-surface2 border border-border flex items-center justify-center text-4xl">
              {selectedAgent.emoji}
            </div>
            <div>
              <h2 className="font-bold text-base text-white">{selectedAgent.name}</h2>
              <p className="text-xs text-gray-500 mt-0.5">{selectedAgent.description}</p>
            </div>
          </div>

          {/* Metadata */}
          <div className="space-y-2">
            {fields.map(f => (
              <div key={f.label} className="flex items-center gap-2.5 py-1.5 border-b border-border/50">
                <f.Icon size={12} className="text-gray-600 shrink-0"/>
                <span className="text-[11px] text-gray-500 w-20 shrink-0">{f.label}</span>
                <span className="text-[11px] text-gray-300 font-mono truncate">{f.value}</span>
              </div>
            ))}
          </div>

          {/* Run button */}
          {selectedAgent.script && (
            <button onClick={handleRun}
              disabled={selectedAgent.status === 'running'}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-blue/15 text-blue border border-blue/25 hover:bg-blue/25 disabled:opacity-40 transition-colors text-sm font-medium">
              <Play size={12} fill="currentColor"/> Chạy ngay
            </button>
          )}
        </div>

        {/* Right: live activity */}
        <div className="flex-1 overflow-hidden">
          <ActivityStream agentId={selectedAgent.id}/>
        </div>
      </div>
    </div>
  )
}
