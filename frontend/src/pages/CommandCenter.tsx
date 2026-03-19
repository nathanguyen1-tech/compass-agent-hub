import { useState } from 'react'
import { useAgentStore } from '../stores/agentStore'
import AgentCard from '../components/AgentCard'
import ActivityStream from '../components/ActivityStream'
import AddAgentModal from '../components/AddAgentModal'

export default function CommandCenter() {
  const [showAdd, setShowAdd] = useState(false)
  const { agents, approvals } = useAgentStore()
  const running = agents.filter(a => a.status === 'running')
  const pending = approvals.filter(a => a.status === 'pending')

  const handleApprove = async (id: string) => {
    await fetch(`/api/approvals/${id}/approve`, { method: 'POST' })
    window.location.reload()
  }
  const handleReject = async (id: string) => {
    await fetch(`/api/approvals/${id}/reject`, { method: 'POST' })
    window.location.reload()
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: Agents */}
      <div className="w-72 shrink-0 border-r border-border flex flex-col overflow-hidden">
        {/* Stats */}
        <div className="grid grid-cols-3 border-b border-border">
          {[
            { label: 'Tổng', value: agents.length, color: 'text-white' },
            { label: 'Chạy', value: running.length, color: 'text-blue' },
            { label: 'Duyệt', value: pending.length, color: pending.length > 0 ? 'text-yellow' : 'text-gray-500' },
          ].map(s => (
            <div key={s.label} className="text-center py-3 border-r border-border last:border-0">
              <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-xs text-gray-500">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Active agents highlight */}
        {running.length > 0 && (
          <div className="px-3 py-2 bg-blue/5 border-b border-blue/20">
            <p className="text-xs text-blue font-medium mb-1.5">🔵 Đang hoạt động</p>
            {running.map(a => (
              <div key={a.id} className="text-xs text-gray-300 flex gap-1.5">
                <span>{a.emoji}</span><span>{a.name}</span>
              </div>
            ))}
          </div>
        )}

        {/* Agent list */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">⚔️ Tướng lĩnh</span>
            <button onClick={() => setShowAdd(true)} className="text-xs text-blue hover:underline">+ Thêm</button>
          </div>
          {agents.map(a => <AgentCard key={a.id} agent={a}/>)}
        </div>
      </div>

      {/* Center: Approvals */}
      <div className="flex-1 flex flex-col overflow-hidden border-r border-border">
        <div className="px-4 py-2.5 border-b border-border shrink-0">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            ⏳ Hàng chờ phê duyệt
          </span>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {pending.length === 0 ? (
            <div className="text-center mt-12 text-gray-600">
              <div className="text-3xl mb-2">✅</div>
              <p className="text-sm">Không có gì cần duyệt</p>
            </div>
          ) : (
            pending.map(appr => {
              const agent = agents.find(a => a.id === appr.agent_id)
              return (
                <div key={appr.id} className="bg-surface border border-violet/30 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xl">{agent?.emoji}</span>
                    <div>
                      <p className="font-semibold text-sm">{agent?.name}</p>
                      <p className="text-xs text-gray-400">
                        {new Date(appr.created_at).toLocaleString('vi-VN')}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleApprove(appr.id)}
                      className="flex-1 py-1.5 text-sm rounded bg-green/20 text-green border border-green/30 hover:bg-green/30 transition-colors"
                    >
                      ✅ Duyệt
                    </button>
                    <button
                      onClick={() => handleReject(appr.id)}
                      className="flex-1 py-1.5 text-sm rounded bg-red/20 text-red border border-red/30 hover:bg-red/30 transition-colors"
                    >
                      ❌ Từ chối
                    </button>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Right: Activity Stream */}
      <div className="w-96 shrink-0 flex flex-col overflow-hidden">
        <ActivityStream/>
      </div>

      {/* Modal */}
      {showAdd && <AddAgentModal onClose={() => setShowAdd(false)}/>}
    </div>
  )
}
