import { useState } from 'react'
import { Users, Cpu, Clock, CheckCircle2, XCircle, Plus } from 'lucide-react'
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

      {/* ── Left sidebar: Agents ───────────────────────────── */}
      <div className="w-64 shrink-0 border-r border-border flex flex-col overflow-hidden">
        {/* Stats */}
        <div className="grid grid-cols-3 border-b border-border">
          {[
            { label: 'Tổng',  value: agents.length,  Icon: Users, color: 'text-gray-300' },
            { label: 'Chạy',  value: running.length, Icon: Cpu,   color: running.length > 0 ? 'text-blue' : 'text-gray-600' },
            { label: 'Duyệt', value: pending.length, Icon: Clock, color: pending.length > 0 ? 'text-yellow' : 'text-gray-600' },
          ].map(s => (
            <div key={s.label} className="flex flex-col items-center py-3 border-r border-border last:border-0">
              <s.Icon size={14} className={s.color}/>
              <span className={`text-lg font-bold mt-0.5 ${s.color}`}>{s.value}</span>
              <span className="text-[10px] text-gray-600">{s.label}</span>
            </div>
          ))}
        </div>

        {/* Running highlight */}
        {running.length > 0 && (
          <div className="px-3 py-2 bg-blue/5 border-b border-blue/10">
            <p className="text-[10px] text-blue font-semibold uppercase tracking-wider mb-1">Đang chạy</p>
            {running.map(a => (
              <div key={a.id} className="flex items-center gap-1.5 text-xs text-gray-300">
                <span>{a.emoji}</span><span>{a.name}</span>
              </div>
            ))}
          </div>
        )}

        {/* Agent list */}
        <div className="flex-1 overflow-y-auto py-2">
          <div className="flex items-center justify-between px-3 mb-1">
            <span className="text-[10px] text-gray-600 uppercase tracking-wider font-semibold">Tướng lĩnh</span>
            <button onClick={() => setShowAdd(true)}
              className="flex items-center gap-0.5 text-[11px] text-gray-500 hover:text-blue transition-colors">
              <Plus size={11}/> Thêm
            </button>
          </div>
          {agents.map(a => <AgentCard key={a.id} agent={a}/>)}
        </div>
      </div>

      {/* ── Center: Approvals ──────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden border-r border-border">
        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border shrink-0">
          <Clock size={13} className="text-gray-500"/>
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Hàng chờ phê duyệt</span>
          {pending.length > 0 && (
            <span className="ml-auto text-[10px] font-bold text-yellow bg-yellow/10 border border-yellow/20 px-2 py-0.5 rounded-full">
              {pending.length} chờ
            </span>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {pending.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-700 gap-3">
              <div className="w-12 h-12 rounded-full bg-surface2 flex items-center justify-center">
                <CheckCircle2 size={22} strokeWidth={1.5}/>
              </div>
              <p className="text-sm text-gray-600">Không có gì cần duyệt</p>
            </div>
          ) : pending.map(appr => {
            const agent = agents.find(a => a.id === appr.agent_id)
            return (
              <div key={appr.id} className="bg-surface border border-border rounded-xl p-4 hover:border-violet/30 transition-colors">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-9 h-9 rounded-lg bg-surface2 flex items-center justify-center text-xl">
                    {agent?.emoji ?? '🤖'}
                  </div>
                  <div>
                    <p className="font-semibold text-sm text-white">{agent?.name}</p>
                    <p className="text-[11px] text-gray-500">
                      {new Date(appr.created_at).toLocaleString('vi-VN')}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleApprove(appr.id)}
                    className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs rounded-lg bg-green/10 text-green border border-green/20 hover:bg-green/20 transition-colors font-medium">
                    <CheckCircle2 size={12}/> Duyệt
                  </button>
                  <button onClick={() => handleReject(appr.id)}
                    className="flex-1 flex items-center justify-center gap-1.5 py-1.5 text-xs rounded-lg bg-red/10 text-red border border-red/20 hover:bg-red/20 transition-colors font-medium">
                    <XCircle size={12}/> Từ chối
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Right: Activity Stream ────────────────────────── */}
      <div className="w-96 shrink-0 flex flex-col overflow-hidden">
        <ActivityStream/>
      </div>

      {showAdd && <AddAgentModal onClose={() => setShowAdd(false)}/>}
    </div>
  )
}
