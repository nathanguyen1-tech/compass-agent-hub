import { useEffect, useRef } from 'react'
import { useAgentStore } from '../stores/agentStore'

const LEVEL_STYLE: Record<string, string> = {
  success:  'text-green',
  error:    'text-red',
  warning:  'text-yellow',
  progress: 'text-violet',
  info:     'text-gray-300',
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
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border shrink-0">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">📡 Activity Stream</span>
        <span className="ml-auto w-1.5 h-1.5 rounded-full bg-cyan animate-pulse"/>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 font-mono text-xs space-y-0.5">
        {filtered.length === 0 ? (
          <p className="text-gray-600 text-center mt-8">Chưa có hoạt động</p>
        ) : (
          filtered.map((evt) => {
            const agent = getAgent(evt.agent_id)
            const time  = new Date(evt.ts).toLocaleTimeString('vi-VN')
            return (
              <div key={evt.id} className="flex gap-2 items-start py-0.5 animate-slide-in">
                <span className="text-gray-600 shrink-0">{time}</span>
                {!agentId && agent && (
                  <span className="shrink-0" title={agent.name}>{agent.emoji}</span>
                )}
                <span className={`${LEVEL_STYLE[evt.level] ?? 'text-gray-300'} break-all`}>
                  {evt.message}
                </span>
              </div>
            )
          })
        )}
        <div ref={bottomRef}/>
      </div>
    </div>
  )
}
