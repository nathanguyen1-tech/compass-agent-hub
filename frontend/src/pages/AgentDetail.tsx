import { useAgentStore } from '../stores/agentStore'
import ActivityStream from '../components/ActivityStream'

export default function AgentDetail() {
  const { selectedAgent, setView, setSelectedAgent } = useAgentStore()

  if (!selectedAgent) {
    setView('command-center')
    return null
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border bg-surface shrink-0">
        <button
          onClick={() => { setSelectedAgent(null); setView('command-center') }}
          className="text-xs text-gray-400 hover:text-white transition-colors"
        >
          ← Bản Chỉ Huy
        </button>
        <span className="text-gray-600">›</span>
        <span className="text-sm font-semibold">{selectedAgent.emoji} {selectedAgent.name}</span>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: Agent info */}
        <div className="w-72 shrink-0 border-r border-border p-4 overflow-y-auto">
          <div className="text-4xl mb-2">{selectedAgent.emoji}</div>
          <h2 className="text-lg font-bold">{selectedAgent.name}</h2>
          <p className="text-sm text-gray-400 mt-1">{selectedAgent.description}</p>

          <div className="mt-4 space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-gray-500">Trạng thái</span>
              <span className="font-medium capitalize">{selectedAgent.status}</span>
            </div>
            {selectedAgent.last_run && (
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">Lần chạy cuối</span>
                <span>{new Date(selectedAgent.last_run).toLocaleString('vi-VN')}</span>
              </div>
            )}
            {selectedAgent.openclaw_agent_id && (
              <div className="flex justify-between text-xs">
                <span className="text-gray-500">OpenClaw ID</span>
                <span className="font-mono">{selectedAgent.openclaw_agent_id}</span>
              </div>
            )}
          </div>

          {selectedAgent.script && (
            <button className="mt-4 w-full py-2 text-sm rounded bg-blue/20 text-blue border border-blue/30 hover:bg-blue/30 transition-colors">
              ▶ Chạy ngay
            </button>
          )}
        </div>

        {/* Right: Live activity */}
        <div className="flex-1 overflow-hidden">
          <ActivityStream agentId={selectedAgent.id}/>
        </div>
      </div>
    </div>
  )
}
