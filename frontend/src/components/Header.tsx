import { LayoutDashboard, Swords, Activity, Wifi, WifiOff, Loader2, Clock } from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'

export default function Header() {
  const { view, setView, connected, agents, approvals } = useAgentStore()
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
        <span className="text-[10px] text-gray-600 font-mono">v2</span>
      </div>

      {/* Nav */}
      <nav className="flex gap-1">
        <NavBtn active={view === 'command-center'} onClick={() => setView('command-center')}
          icon={<LayoutDashboard size={13}/>}>
          Bản Chỉ Huy
        </NavBtn>
        <NavBtn active={view === 'general'} onClick={() => setView('general')}
          icon={<Swords size={13}/>}>
          Đại Tướng
          {pending > 0 && <Badge>{pending}</Badge>}
        </NavBtn>
      </nav>

      {/* Right status */}
      <div className="ml-auto flex items-center gap-4 text-xs">
        {running > 0 && (
          <span className="flex items-center gap-1.5 text-blue">
            <Loader2 size={11} className="animate-spin"/>
            <span>{running} đang chạy</span>
          </span>
        )}
        {pending > 0 && (
          <span className="flex items-center gap-1.5 text-yellow">
            <Clock size={11}/>
            <span>{pending} chờ duyệt</span>
          </span>
        )}
        <span className="flex items-center gap-1.5 text-gray-500">
          {connected
            ? <><Wifi size={11} className="text-green"/><span className="text-green">Live</span></>
            : <><WifiOff size={11} className="text-red"/><span className="text-red">Offline</span></>
          }
        </span>
      </div>
    </header>
  )
}

function NavBtn({ active, onClick, icon, children }: {
  active: boolean; onClick: () => void
  icon: React.ReactNode; children: React.ReactNode
}) {
  return (
    <button onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
        active
          ? 'bg-blue/15 text-blue border border-blue/25'
          : 'text-gray-400 hover:text-white hover:bg-white/5'
      }`}>
      {icon}{children}
    </button>
  )
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="ml-1 px-1.5 py-0.5 rounded-full bg-red text-white text-[10px] leading-none font-bold">
      {children}
    </span>
  )
}
