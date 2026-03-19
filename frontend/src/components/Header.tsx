import { LayoutDashboard, Swords, Network, MessageSquareMore, Activity, Wifi, WifiOff, Loader2, Clock } from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'

type View = 'command-center' | 'general' | 'agent-detail' | 'topology' | 'message-bus'

const NAV: { view: View; Icon: React.ElementType; label: string }[] = [
  { view: 'command-center', Icon: LayoutDashboard,    label: 'Bản Chỉ Huy' },
  { view: 'topology',       Icon: Network,            label: 'Topology' },
  { view: 'message-bus',    Icon: MessageSquareMore,  label: 'Message Bus' },
  { view: 'general',        Icon: Swords,             label: 'Đại Tướng' },
]

export default function Header() {
  const { view, setView, connected, agents, approvals, a2aMessages } = useAgentStore()
  const running = agents.filter(a => a.status === 'running').length
  const pending = approvals.filter(a => a.status === 'pending').length

  return (
    <header className="flex items-center gap-2 px-4 h-12 bg-surface border-b border-border shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2 mr-3">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue to-violet flex items-center justify-center">
          <Activity size={14} className="text-white"/>
        </div>
        <span className="font-bold text-sm tracking-tight text-white">Agent Hub</span>
        <span className="text-[10px] text-gray-600 font-mono">v3</span>
      </div>

      {/* Nav */}
      <nav className="flex gap-0.5">
        {NAV.map(({ view: v, Icon, label }) => (
          <button key={v} onClick={() => setView(v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              view === v || (v === 'command-center' && view === 'agent-detail')
                ? 'bg-blue/15 text-blue border border-blue/25'
                : 'text-gray-500 hover:text-white hover:bg-white/5'
            }`}>
            <Icon size={12}/>
            {label}
            {v === 'general' && pending > 0 && (
              <span className="px-1 py-0.5 rounded-full bg-red text-white text-[10px] leading-none font-bold">{pending}</span>
            )}
            {v === 'message-bus' && a2aMessages.length > 0 && (
              <span className="px-1 py-0.5 rounded-full bg-violet/80 text-white text-[10px] leading-none font-bold">{a2aMessages.length}</span>
            )}
          </button>
        ))}
      </nav>

      {/* Status */}
      <div className="ml-auto flex items-center gap-4 text-xs">
        {running > 0 && (
          <span className="flex items-center gap-1.5 text-blue">
            <Loader2 size={11} className="animate-spin"/>
            {running} đang chạy
          </span>
        )}
        {pending > 0 && (
          <span className="flex items-center gap-1.5 text-yellow">
            <Clock size={11}/>{pending} chờ duyệt
          </span>
        )}
        <span className="flex items-center gap-1.5">
          {connected
            ? <><Wifi size={11} className="text-green"/><span className="text-green">Live</span></>
            : <><WifiOff size={11} className="text-red"/><span className="text-red">Offline</span></>
          }
        </span>
      </div>
    </header>
  )
}
