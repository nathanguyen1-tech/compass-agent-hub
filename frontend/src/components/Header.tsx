import { useAgentStore } from '../stores/agentStore'

export default function Header() {
  const { view, setView, connected, agents, approvals } = useAgentStore()
  const running  = agents.filter(a => a.status === 'running').length
  const pending  = approvals.filter(a => a.status === 'pending').length

  return (
    <header className="flex items-center gap-3 px-4 h-12 bg-surface border-b border-border shrink-0">
      <div className="flex items-center gap-2 mr-2">
        <span className="text-lg">🏯</span>
        <span className="font-bold text-sm text-white">Agent Hub</span>
        <span className="text-xs text-gray-500 hidden sm:block">v2</span>
      </div>

      <nav className="flex gap-1">
        <NavBtn active={view === 'command-center'} onClick={() => setView('command-center')}>
          🏯 Bản Chỉ Huy
        </NavBtn>
        <NavBtn active={view === 'general'} onClick={() => setView('general')}>
          ⚔️ Đại Tướng
          {pending > 0 && <Badge>{pending}</Badge>}
        </NavBtn>
      </nav>

      <div className="ml-auto flex items-center gap-3 text-xs text-gray-400">
        {running > 0 && (
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-blue animate-pulse"/>
            {running} đang chạy
          </span>
        )}
        {pending > 0 && (
          <span className="flex items-center gap-1.5 text-yellow">
            <span>⏳</span>{pending} chờ duyệt
          </span>
        )}
        <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green' : 'bg-red'}`}/>
      </div>
    </header>
  )
}

function NavBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
        active ? 'bg-blue/20 text-blue border border-blue/30' : 'text-gray-400 hover:text-white hover:bg-white/5'
      }`}
    >
      {children}
    </button>
  )
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="ml-1 px-1.5 py-0.5 rounded-full bg-red text-white text-xs leading-none">
      {children}
    </span>
  )
}
