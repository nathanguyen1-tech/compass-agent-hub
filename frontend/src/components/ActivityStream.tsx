import { useEffect, useRef } from 'react'
import { Radio, CheckCircle2, XCircle, AlertTriangle, Info, Zap } from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'

const LEVEL_CONFIG: Record<string, { color: string; Icon: React.ElementType }> = {
  success:  { color: 'text-green',  Icon: CheckCircle2 },
  error:    { color: 'text-red',    Icon: XCircle },
  warning:  { color: 'text-yellow', Icon: AlertTriangle },
  progress: { color: 'text-violet', Icon: Zap },
  info:     { color: 'text-gray-400', Icon: Info },
}

export default function ActivityStream({ agentId }: { agentId?: string }) {
  const { events, agents } = useAgentStore()
  const bottomRef = useRef<HTMLDivElement>(null)
  const filtered  = agentId ? events.filter(e => e.agent_id === agentId) : events

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [filtered.length])

  const getAgent = (id: string) => agents.find(a => a.id === id)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border shrink-0">
        <Radio size={13} className="text-cyan"/>
        <span className="text-xs font-semibold text-gray-300 tracking-wide">Activity Stream</span>
        <span className="ml-auto flex items-center gap-1 text-[10px] text-cyan">
          <span className="w-1 h-1 rounded-full bg-cyan animate-pulse"/>LIVE
        </span>
      </div>

      {/* Events */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-0.5">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-700 gap-2">
            <Radio size={28} strokeWidth={1}/>
            <p className="text-xs">Chưa có hoạt động</p>
          </div>
        ) : filtered.map((evt) => {
          const agent   = getAgent(evt.agent_id)
          const time    = new Date(evt.ts).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
          const cfg     = LEVEL_CONFIG[evt.level] ?? LEVEL_CONFIG.info
          const LvlIcon = cfg.Icon
          return (
            <div key={evt.id} className="flex gap-2 items-start py-0.5 group animate-slide-in">
              <span className="text-gray-600 text-[10px] font-mono shrink-0 mt-0.5 tabular-nums">{time}</span>
              <LvlIcon size={11} className={`${cfg.color} shrink-0 mt-0.5`}/>
              {!agentId && agent && (
                <span className="text-sm shrink-0 leading-none mt-px" title={agent.name}>{agent.emoji}</span>
              )}
              <span className={`text-[11px] leading-relaxed ${cfg.color} break-all`}>
                {evt.message}
              </span>
            </div>
          )
        })}
        <div ref={bottomRef}/>
      </div>
    </div>
  )
}
