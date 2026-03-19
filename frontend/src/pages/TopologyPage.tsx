import { useEffect, useState } from 'react'
import { Network, RefreshCw, Link2, MonitorSmartphone, Bot, Wifi } from 'lucide-react'
import type { Topology, Binding } from '../types'

const CHANNEL_ICONS: Record<string, string> = {
  discord: '🎮', telegram: '✈️', whatsapp: '📱', signal: '🔒',
  webchat: '🌐', imessage: '💬', slack: '💼', irc: '📻',
  default: '📡',
}

function ChannelBadge({ channel }: { channel: string }) {
  const icon = CHANNEL_ICONS[channel] ?? CHANNEL_ICONS.default
  return (
    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface2 border border-border text-xs text-gray-300">
      <span>{icon}</span>{channel || 'all'}
    </span>
  )
}

export default function TopologyPage() {
  const [topo, setTopo]       = useState<Topology | null>(null)
  const [loading, setLoading] = useState(true)
  const [sessions, setSessions] = useState<Record<string, number>>({})

  const load = async () => {
    setLoading(true)
    const [t, s] = await Promise.all([
      fetch('/api/topology').then(r => r.json()),
      fetch('/api/topology/sessions').then(r => r.json()),
    ])
    setTopo(t)
    // Count active sessions per agent
    const counts: Record<string, number> = {}
    for (const sess of s) counts[sess.agent_id] = (counts[sess.agent_id] ?? 0) + 1
    setSessions(counts)
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  if (loading || !topo) return (
    <div className="flex items-center justify-center h-full text-gray-600 gap-2">
      <RefreshCw size={16} className="animate-spin"/><span>Đang tải topology...</span>
    </div>
  )

  const agentBindings = (agentId: string) =>
    topo.bindings.filter(b => b.agent_id === agentId)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-5 py-3 border-b border-border bg-surface shrink-0">
        <Network size={14} className="text-blue"/>
        <span className="text-sm font-semibold text-white">Network Topology</span>
        {topo.a2a_enabled && (
          <span className="flex items-center gap-1 text-[10px] text-violet bg-violet/10 border border-violet/20 px-2 py-0.5 rounded-full">
            <Link2 size={9}/> A2A Enabled
          </span>
        )}
        <button onClick={load}
          className="ml-auto flex items-center gap-1 text-xs text-gray-500 hover:text-white transition-colors">
          <RefreshCw size={11}/> Refresh
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5">

        {/* Summary stats */}
        <div className="grid grid-cols-4 gap-3 mb-6">
          {[
            { icon: Bot,              label: 'Agents',    value: topo.agents.length,   color: 'text-blue' },
            { icon: Link2,            label: 'Bindings',  value: topo.bindings.length, color: 'text-violet' },
            { icon: MonitorSmartphone,label: 'Channels',  value: Object.keys(topo.accounts).length, color: 'text-cyan' },
            { icon: Wifi,             label: 'Active',    value: Object.values(sessions).reduce((a,b) => a+b, 0), color: 'text-green' },
          ].map(s => (
            <div key={s.label} className="bg-surface border border-border rounded-xl p-3 text-center">
              <s.icon size={16} className={`mx-auto mb-1 ${s.color}`}/>
              <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-[11px] text-gray-500">{s.label}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-5">
          {/* Left: Agents + their bindings */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <Bot size={12}/> Agents & Routing
            </h3>
            <div className="space-y-3">
              {topo.agents.map(agent => {
                const binds   = agentBindings(agent.id)
                const active  = sessions[agent.id] ?? 0
                return (
                  <div key={agent.id} className="bg-surface border border-border rounded-xl p-4 hover:border-blue/30 transition-colors">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-9 h-9 rounded-lg bg-surface2 flex items-center justify-center text-xl">{agent.emoji}</div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm text-white">{agent.name}</span>
                          {active > 0 && (
                            <span className="flex items-center gap-0.5 text-[10px] text-cyan">
                              <span className="w-1 h-1 rounded-full bg-cyan animate-pulse"/>
                              {active} active
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className="text-[11px] text-gray-500 font-mono">{agent.id}</span>
                          {agent.model && (
                            <span className="text-[10px] text-gray-600 bg-white/5 px-1.5 py-0.5 rounded font-mono">
                              {agent.model.split('/').pop()}
                            </span>
                          )}
                          {agent.source === 'openclaw' && (
                            <span className="text-[10px] text-blue bg-blue/10 border border-blue/20 px-1.5 py-0.5 rounded">auto</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Bindings */}
                    {binds.length > 0 ? (
                      <div className="space-y-1.5">
                        <p className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">Nhận từ</p>
                        {binds.map((b, i) => (
                          <div key={i} className="flex items-center gap-1.5 flex-wrap">
                            <ChannelBadge channel={b.channel}/>
                            {b.account_id && <span className="text-[10px] text-gray-500">acct: {b.account_id}</span>}
                            {b.peer_kind && (
                              <span className="text-[10px] text-gray-500">
                                {b.peer_kind}: {b.peer_id.slice(0,12)}{b.peer_id.length > 12 ? '...' : ''}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[11px] text-gray-700 italic">Không có binding — nhận từ webchat</p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* Right: Channel accounts */}
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <MonitorSmartphone size={12}/> Channel Accounts
            </h3>

            {Object.keys(topo.accounts).length === 0 ? (
              <div className="bg-surface border border-border rounded-xl p-6 text-center text-gray-600">
                <MonitorSmartphone size={24} strokeWidth={1} className="mx-auto mb-2"/>
                <p className="text-sm">Chưa cấu hình channel accounts</p>
                <p className="text-xs mt-1">Thêm vào ~/.openclaw/openclaw.json</p>
              </div>
            ) : (
              <div className="space-y-3">
                {Object.entries(topo.accounts).map(([ch, accs]) => (
                  <div key={ch} className="bg-surface border border-border rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="text-lg">{CHANNEL_ICONS[ch] ?? '📡'}</span>
                      <span className="font-semibold text-sm capitalize text-white">{ch}</span>
                      <span className="text-[10px] text-gray-600 ml-auto">{accs.length} account{accs.length > 1 ? 's' : ''}</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {accs.map(acc => (
                        <span key={acc} className="px-2 py-0.5 text-xs rounded bg-surface2 border border-border text-gray-300 font-mono">
                          {acc}
                        </span>
                      ))}
                    </div>
                    {/* Which agents bind this channel */}
                    <div className="mt-2 flex flex-wrap gap-1">
                      {topo.bindings
                        .filter(b => b.channel === ch)
                        .map(b => {
                          const a = topo.agents.find(ag => ag.id === b.agent_id)
                          return a ? (
                            <span key={b.agent_id} className="text-[10px] flex items-center gap-0.5 text-gray-500">
                              → {a.emoji} {a.name}
                            </span>
                          ) : null
                        })}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* A2A info */}
            <div className={`mt-4 rounded-xl p-4 border ${topo.a2a_enabled ? 'border-violet/30 bg-violet/5' : 'border-border bg-surface'}`}>
              <div className="flex items-center gap-2 mb-1">
                <Link2 size={13} className={topo.a2a_enabled ? 'text-violet' : 'text-gray-600'}/>
                <span className="text-xs font-semibold text-white">Agent-to-Agent Messaging</span>
                <span className={`ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full ${
                  topo.a2a_enabled ? 'text-violet bg-violet/15 border border-violet/25' : 'text-gray-600 bg-white/5 border border-border'
                }`}>
                  {topo.a2a_enabled ? 'ENABLED' : 'DISABLED'}
                </span>
              </div>
              <p className="text-[11px] text-gray-500">
                {topo.a2a_enabled
                  ? 'Agents có thể nhắn cho nhau. Xem Message Bus để theo dõi.'
                  : 'Bật trong openclaw.json: tools.agentToAgent.enabled = true'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
