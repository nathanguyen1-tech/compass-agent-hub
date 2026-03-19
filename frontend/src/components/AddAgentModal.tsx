import { useState } from 'react'
import { X, Check } from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'

interface Props { onClose: () => void }

const EMOJI_OPTIONS = ['🤖','🏗️','🩺','🏥','🔍','📊','⚙️','🚀','🛡️','📝','🔮','⚡','🎯','🧠','🌐','🔧','📡','🗂️','⚖️','🔐']

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-400 mb-1">
        {label}{hint && <span className="ml-1 text-gray-600 font-normal">{hint}</span>}
      </label>
      {children}
    </div>
  )
}

const INPUT_CLS = "w-full bg-bg border border-border rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue/60 transition-colors"

export default function AddAgentModal({ onClose }: Props) {
  const { setAgents } = useAgentStore()
  const [form, setForm] = useState({
    id: '', name: '', emoji: '🤖', description: '',
    script: '', openclaw_agent_id: '', requires_approval: false,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const set = (k: string, v: string | boolean) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.id.trim() || !form.name.trim()) { setError('ID và Tên là bắt buộc'); return }
    const payload = { ...form, id: form.id.trim().toLowerCase().replace(/\s+/g, '-') }
    setLoading(true); setError('')
    try {
      const res  = await fetch('/api/agents', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Lỗi server')
      const updated = await fetch('/api/agents').then(r => r.json())
      setAgents(updated)
      onClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="bg-surface border border-border rounded-2xl w-[460px] max-h-[88vh] overflow-y-auto shadow-2xl animate-slide-in">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="font-bold text-sm text-white">Thêm Tướng Lĩnh Mới</h2>
          <button onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-gray-500 hover:text-white hover:bg-white/10 transition-colors">
            <X size={14}/>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* Emoji */}
          <Field label="Biểu tượng">
            <div className="flex flex-wrap gap-1.5">
              {EMOJI_OPTIONS.map(em => (
                <button key={em} type="button" onClick={() => set('emoji', em)}
                  className={`w-9 h-9 text-lg rounded-lg border transition-all ${
                    form.emoji === em
                      ? 'border-blue bg-blue/20 scale-110'
                      : 'border-border hover:border-gray-500 bg-surface2'
                  }`}>{em}</button>
              ))}
            </div>
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Tên" hint="*">
              <input value={form.name} onChange={e => {
                set('name', e.target.value)
                if (!form.id) set('id', e.target.value.toLowerCase().replace(/\s+/g, '-'))
              }} placeholder="VD: DataBot" className={INPUT_CLS}/>
            </Field>
            <Field label="ID" hint="*">
              <input value={form.id} onChange={e => set('id', e.target.value)}
                placeholder="data-bot" className={`${INPUT_CLS} font-mono`}/>
            </Field>
          </div>

          <Field label="Mô tả">
            <input value={form.description} onChange={e => set('description', e.target.value)}
              placeholder="Mô tả ngắn về nhiệm vụ..." className={INPUT_CLS}/>
          </Field>

          <Field label="OpenClaw Agent ID" hint="(nếu là chat agent)">
            <input value={form.openclaw_agent_id} onChange={e => set('openclaw_agent_id', e.target.value)}
              placeholder="hub-keeper, main..." className={`${INPUT_CLS} font-mono`}/>
          </Field>

          <Field label="Script" hint="(để trống nếu là chat agent)">
            <input value={form.script} onChange={e => set('script', e.target.value)}
              placeholder="/path/to/script.sh" className={`${INPUT_CLS} font-mono`}/>
          </Field>

          {/* Toggle */}
          <label className="flex items-center gap-3 cursor-pointer py-1">
            <button type="button" onClick={() => set('requires_approval', !form.requires_approval)}
              className={`relative w-9 h-5 rounded-full transition-colors ${form.requires_approval ? 'bg-blue' : 'bg-gray-700'}`}>
              <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow ${form.requires_approval ? 'translate-x-4' : 'translate-x-0.5'}`}/>
            </button>
            <span className="text-sm text-gray-300">Yêu cầu phê duyệt trước khi chạy</span>
          </label>

          {error && (
            <p className="text-red text-xs bg-red/10 border border-red/20 rounded-lg px-3 py-2">{error}</p>
          )}

          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 py-2 rounded-lg border border-border text-sm text-gray-400 hover:border-gray-500 hover:text-white transition-colors">
              Hủy
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-blue text-white text-sm font-semibold hover:bg-blue/80 disabled:opacity-50 transition-colors">
              {loading ? 'Đang thêm...' : <><Check size={14}/> Thêm Agent</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
