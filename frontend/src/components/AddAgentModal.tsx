import { useState } from 'react'
import { useAgentStore } from '../stores/agentStore'

interface Props { onClose: () => void }

const EMOJI_OPTIONS = ['🤖','🏗️','🩺','🏥','🔍','📊','⚙️','🚀','🛡️','📝','🔮','⚡','🎯','🧠','🌐']

export default function AddAgentModal({ onClose }: Props) {
  const { setAgents } = useAgentStore()
  const [form, setForm] = useState({
    id: '', name: '', emoji: '🤖', description: '',
    script: '', openclaw_agent_id: '', requires_approval: false,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const set = (k: string, v: string | boolean) =>
    setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.id.trim() || !form.name.trim()) {
      setError('ID và Tên là bắt buộc'); return
    }
    // Auto slug ID
    const payload = { ...form, id: form.id.trim().toLowerCase().replace(/\s+/g, '-') }
    setLoading(true); setError('')
    try {
      const res = await fetch('/api/agents', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Lỗi server')

      // Refresh danh sách
      const updated = await fetch('/api/agents').then(r => r.json())
      setAgents(updated)
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="bg-surface border border-border rounded-2xl w-[460px] max-h-[90vh] overflow-y-auto shadow-2xl animate-slide-in">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="font-bold text-base">✨ Thêm Tướng Lĩnh Mới</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl leading-none">×</button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Emoji picker */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Biểu tượng</label>
            <div className="flex flex-wrap gap-1.5">
              {EMOJI_OPTIONS.map(em => (
                <button key={em} type="button" onClick={() => set('emoji', em)}
                  className={`w-9 h-9 text-xl rounded-lg border transition-colors ${
                    form.emoji === em
                      ? 'border-blue bg-blue/20'
                      : 'border-border hover:border-gray-500 bg-surface2'
                  }`}>
                  {em}
                </button>
              ))}
            </div>
          </div>

          {/* Name + ID */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Tên <span className="text-red">*</span></label>
              <input value={form.name} onChange={e => {
                set('name', e.target.value)
                if (!form.id) set('id', e.target.value.toLowerCase().replace(/\s+/g,'-'))
              }}
                placeholder="VD: DataBot"
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">ID <span className="text-red">*</span></label>
              <input value={form.id} onChange={e => set('id', e.target.value)}
                placeholder="data-bot"
                className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-blue"
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">Mô tả</label>
            <input value={form.description} onChange={e => set('description', e.target.value)}
              placeholder="Mô tả ngắn về nhiệm vụ..."
              className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue"
            />
          </div>

          {/* OpenClaw Agent ID */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              OpenClaw Agent ID
              <span className="ml-1 text-gray-600">(nếu là chat agent)</span>
            </label>
            <input value={form.openclaw_agent_id} onChange={e => set('openclaw_agent_id', e.target.value)}
              placeholder="VD: hub-keeper, main..."
              className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-blue"
            />
          </div>

          {/* Script */}
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Script
              <span className="ml-1 text-gray-600">(để trống nếu là chat agent)</span>
            </label>
            <input value={form.script} onChange={e => set('script', e.target.value)}
              placeholder="/path/to/script.sh"
              className="w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:border-blue"
            />
          </div>

          {/* Requires approval */}
          <label className="flex items-center gap-3 cursor-pointer">
            <div
              onClick={() => set('requires_approval', !form.requires_approval)}
              className={`relative w-10 h-5 rounded-full transition-colors ${form.requires_approval ? 'bg-blue' : 'bg-gray-700'}`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${form.requires_approval ? 'translate-x-5' : 'translate-x-0.5'}`}/>
            </div>
            <span className="text-sm text-gray-300">Yêu cầu phê duyệt trước khi chạy</span>
          </label>

          {error && <p className="text-red text-xs bg-red/10 border border-red/20 rounded-lg px-3 py-2">{error}</p>}

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 py-2 rounded-lg border border-border text-sm text-gray-400 hover:border-gray-500 hover:text-white transition-colors">
              Hủy
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 py-2 rounded-lg bg-blue text-white text-sm font-semibold hover:bg-blue/80 disabled:opacity-50 transition-colors">
              {loading ? '⏳ Đang thêm...' : '✅ Thêm Agent'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
