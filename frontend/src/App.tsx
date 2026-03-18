import { useEffect } from 'react'
import { useAgentStore } from './stores/agentStore'
import { useWebSocket } from './hooks/useWebSocket'
import Header from './components/Header'
import CommandCenter from './pages/CommandCenter'
import GeneralChat from './pages/GeneralChat'
import AgentDetail from './pages/AgentDetail'

export default function App() {
  const { view, setAgents, setApprovals, addEvent } = useAgentStore()

  // WebSocket
  useWebSocket()

  // Initial data fetch
  useEffect(() => {
    const fetchAll = async () => {
      const [agentsRes, approvalsRes, activityRes] = await Promise.all([
        fetch('/api/agents'),
        fetch('/api/approvals'),
        fetch('/api/activity?limit=100'),
      ])
      setAgents(await agentsRes.json())
      setApprovals(await approvalsRes.json())
      const events = await activityRes.json()
      events.forEach(addEvent)
    }
    fetchAll()
    const interval = setInterval(fetchAll, 30_000)
    return () => clearInterval(interval)
  }, [setAgents, setApprovals, addEvent])

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Header />
      <main className="flex-1 overflow-hidden">
        {view === 'command-center' && <CommandCenter />}
        {view === 'general'        && <GeneralChat />}
        {view === 'agent-detail'   && <AgentDetail />}
      </main>
    </div>
  )
}
