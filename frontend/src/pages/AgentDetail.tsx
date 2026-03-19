import { useEffect, useState } from 'react'
import { ChevronLeft, Play, Terminal, Clock, Hash, Bot, MessageSquare, Zap } from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'
import ActivityStream from '../components/ActivityStream'
import type { Agent } from '../types'

const CHANNEL_ICONS: Record<string, string> = {
  discord: '🎮', telegram: '✈️', whatsapp: '📱', webchat: '🌐',
  signal: '🔒', imessage: '💬', slack: '💼', unknown: '📡',
}

export default function AgentDetail() {
  const { selectedAgent, setView, setSelectedAgent } = useAgentStore()
  const [detail, setDetail] = useState<Agent | null>(null)

  useEffect(() => {
    if (!selectedAgent) return
    fetch(`/api/agents/${selectedAgent.id}`).then(r => r.json()).then(setDetail)
  }, [selectedAgent?.id])

  if (!selectedAgent) { setView('command-center'); return null }

  const agent   = detail ?? selectedAgent
  const sessions = agent.sessions ?? []
  const active   = sessions.filter(s => s.is_active)
  const msgStats = agent.messages_today

  const handleRun = async () => {
    if (!agent.script) return
    await fetch(`/api/agents/${agent.id}/status`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'running' }),
    })
  }

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
          <span>{agent.emoji}</span>{agent.name}
        </span>
        <span className={`ml-1 text-[10px] font-bold px-2 py-0.5 rounded-full border ${
          agent.status === 'running'  ? 'text-blue border-blue/30 bg-blue/10'
          : agent.status === 'error'  ? 'text-red border-red/30 bg-red/10'
          : 'text-gray-500 border-gray-700 bg-white/5'
        }`}>{agent.status.toUpperCase()}</span>
        {active.length > 0 && (
          <span className="flex items-center gap-1 text-[10px] text-cyan ml-1">
            <span className="w-1 h-1 rounded-full bg-cyan animate-pulse"/>{active.length} active session{active.length > 1 ? 's' : ''}
          </span>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left panel */}
        <div className="w-72 shrink-0 border-r border-border overflow-y-auto">
          <div className="p-4 space-y-4">
            {/* Avatar + info */}
            <div className="flex items-center gap-3">
              <div className="w-14 h-14 rounded-2xl bg-surface2 border border-border flex items-center justify-center text-4xl">
                {agent.emoji}
              </div>
              <div>
                <h2 className="font-bold text-base text-white">{agent.name}</h2>
                <p className="text-xs text-gray-500">{agent.description}</p>
                {agent.model && (
                  <span className="text-[10px] text-gray-600 font-mono bg-white/5 px-1.5 py-0.5 rounded mt-1 inline-block">
                    {agent.model.split('/').pop()}
                  </span>
                )}
              </div>
            </div>

            {/* Metadata fields */}
            <div className="space-y-1.5">
              {[
                { Icon: Hash,     label: 'ID',         value: agent.id },
                { Icon: Bot,      label: 'OC ID',      value: agent.openclaw_agent_id || '—' },
                { Icon: Terminal, label: 'Script',      value: agent.script || '—' },
                { Icon: Clock,    label: 'Lần cuối',   value: agent.last_run ? new Date(agent.last_run).toLocaleString('vi-VN') : '—' },
              ].map(f => (
                <div key={f.label} className="flex items-center gap-2 py-1.5 border-b border-border/40">
                  <f.Icon size={11} className="text-gray-600 shrink-0"/>
                  <span className="text-[11px] text-gray-500 w-14 shrink-0">{f.label}</span>
                  <span className="text-[11px] text-gray-300 font-mono truncate">{f.value}</span>
                </div>
              ))}
            </div>

            {/* A2A stats */}
            {msgStats && msgStats.total > 0 && (
              <div className="bg-violet/5 border border-violet/15 rounded-lg p-3">
                <p className="text-[10px] text-violet font-semibold uppercase tracking-wider mb-2 flex items-center gap-1">
                  <Zap size={9}/> A2A Hôm nay
                </p>
                <div className="grid grid-cols-2 gap-2 text-center text-xs">
                  <div><span className="font-bold text-violet">{msgStats.sent}</span><span className="text-gray-600 block text-[10px]">Gửi</span></div>
                  <div><span className="font-bold text-cyan">{msgStats.received}</span><span className="text-gray-600 block text-[10px]">Nhận</span></div>
                </div>
              </div>
            )}

            {/* Run button */}
            {agent.script && (
              <button onClick={handleRun} disabled={agent.status === 'running'}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-blue/15 text-blue border border-blue/25 hover:bg-blue/25 disabled:opacity-40 transition-colors text-sm font-medium">
                <Play size={12} fill="currentColor"/> Chạy ngay
              </button>
            )}
          </div>

          {/* Session list */}
          {sessions.length > 0 && (
            <div className="border-t border-border px-4 py-3">
              <p className="text-[10px] text-gray-500 font-semibold uppercase tracking-wider mb-2 flex items-center gap-1">
                <MessageSquare size={9}/> Sessions ({sessions.length})
              </p>
              <div className="space-y-1.5">
                {sessions.map(s => (
                  <div key={s.key} className={`flex items-center gap-2 px-2 py-1.5 rounded-lg text-[11px] ${
                    s.is_active ? 'bg-cyan/5 border border-cyan/15' : 'bg-surface2/50'
                  }`}>
                    <span>{CHANNEL_ICONS[s.channel] ?? '📡'}</span>
                    <span className="flex-1 text-gray-300 truncate font-mono">{s.channel}</span>
                    <div className="text-right">
                      {s.is_active
                        ? <span className="text-cyan text-[10px] font-bold">LIVE</span>
                        : <span className="text-gray-600 text-[10px]">{s.updated_ago}</span>
                      }
                      {s.msg_count > 0 && (
                        <span className="text-gray-600 block text-[10px]">{s.msg_count} msgs</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
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
