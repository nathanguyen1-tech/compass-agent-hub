import { useEffect } from 'react'
import { MessageSquareMore, ArrowRight, Zap } from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'
import type { A2AMessage, Agent } from '../types'

function timeFmt(ts: string) {
  const d = new Date(ts)
  const now = Date.now()
  const diff = (now - d.getTime()) / 1000
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff/60)}m ago`
  return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
}

function AgentPill({ id, agents }: { id: string; agents: Agent[] }) {
  const agent = agents.find(a => a.id === id)
  return (
    <span className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-surface2 border border-border text-xs text-white font-medium">
      {agent?.emoji ?? '🤖'} {agent?.name ?? id}
    </span>
  )
}

function MessageRow({ msg, agents }: { msg: A2AMessage; agents: Agent[] }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-xl bg-surface border border-border hover:border-violet/30 transition-colors animate-slide-in">
      <div className="text-[10px] text-gray-600 font-mono shrink-0 mt-0.5 tabular-nums w-16">
        {timeFmt(msg.ts)}
      </div>
      <AgentPill id={msg.from} agents={agents}/>
      <ArrowRight size={13} className="text-violet shrink-0 mt-0.5"/>
      <AgentPill id={msg.to} agents={agents}/>
      <p className="flex-1 text-xs text-gray-400 truncate mt-0.5">{msg.preview}</p>
    </div>
  )
}

export default function MessageBusPage() {
  const { agents, a2aMessages, setView, addA2AMessage } = useAgentStore()

  useEffect(() => {
    // Load initial messages từ API
    fetch('/api/topology/messages?limit=100').then(r => r.json()).then(msgs => {
      for (const m of msgs) addA2AMessage(m)
    })
  }, [])

  // Group by agent pairs
  const pairCounts: Record<string, number> = {}
  for (const m of a2aMessages) {
    const key = [m.from, m.to].sort().join('↔')
    pairCounts[key] = (pairCounts[key] ?? 0) + 1
  }
  const topPairs = Object.entries(pairCounts).sort((a, b) => b[1] - a[1]).slice(0, 5)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-5 py-3 border-b border-border bg-surface shrink-0">
        <MessageSquareMore size={14} className="text-violet"/>
        <span className="text-sm font-semibold text-white">Message Bus</span>
        <span className="text-[11px] text-gray-500">— Agent-to-Agent Communications</span>
        <span className="ml-auto flex items-center gap-1 text-[10px] text-violet">
          <span className="w-1 h-1 rounded-full bg-violet animate-pulse"/>
          Live
        </span>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Timeline */}
        <div className="flex-1 flex flex-col overflow-hidden border-r border-border">
          <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
            <span className="text-[11px] text-gray-500 uppercase tracking-wider font-semibold">Timeline</span>
            <span className="text-[11px] text-gray-600">{a2aMessages.length} messages</span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {a2aMessages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-700 gap-3">
                <div className="w-14 h-14 rounded-2xl bg-surface2 border border-border flex items-center justify-center">
                  <MessageSquareMore size={24} strokeWidth={1}/>
                </div>
                <div className="text-center">
                  <p className="text-sm text-gray-600">Chưa có inter-agent messages</p>
                  <p className="text-xs text-gray-700 mt-1">
                    Messages xuất hiện khi agents dùng sessions_send tool
                  </p>
                </div>
                <button onClick={() => setView('topology')}
                  className="text-xs text-blue hover:underline">
                  Xem Topology →
                </button>
              </div>
            ) : (
              [...a2aMessages].reverse().map(msg => (
                <MessageRow key={msg.id} msg={msg} agents={agents}/>
              ))
            )}
          </div>
        </div>

        {/* Right: Stats */}
        <div className="w-72 shrink-0 p-4 overflow-y-auto space-y-5">
          {/* Top pairs */}
          <div>
            <h3 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <Zap size={10}/> Cặp giao tiếp nhiều nhất
            </h3>
            {topPairs.length === 0 ? (
              <p className="text-xs text-gray-700">Chưa có dữ liệu</p>
            ) : topPairs.map(([pair, count]) => {
              const [a, b] = pair.split('↔')
              const agentA = agents.find(ag => ag.id === a)
              const agentB = agents.find(ag => ag.id === b)
              return (
                <div key={pair} className="flex items-center gap-2 py-2 border-b border-border/50">
                  <span className="text-sm">{agentA?.emoji ?? '🤖'}</span>
                  <ArrowRight size={11} className="text-gray-600"/>
                  <span className="text-sm">{agentB?.emoji ?? '🤖'}</span>
                  <span className="text-xs text-gray-400 flex-1 truncate">
                    {agentA?.name ?? a} ↔ {agentB?.name ?? b}
                  </span>
                  <span className="text-xs font-bold text-violet bg-violet/10 border border-violet/20 px-1.5 py-0.5 rounded">
                    {count}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Per-agent stats */}
          <div>
            <h3 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Per-Agent (hôm nay)
            </h3>
            {agents.filter(a => a.openclaw_agent_id).map(agent => {
              const sent = a2aMessages.filter(m => m.from === agent.id).length
              const recv = a2aMessages.filter(m => m.to   === agent.id).length
              if (sent + recv === 0) return null
              return (
                <div key={agent.id} className="flex items-center gap-2 py-2 border-b border-border/50">
                  <span className="text-sm">{agent.emoji}</span>
                  <span className="text-xs text-gray-300 flex-1 truncate">{agent.name}</span>
                  <div className="flex gap-2 text-[10px]">
                    <span className="text-violet">↑{sent}</span>
                    <span className="text-cyan">↓{recv}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
