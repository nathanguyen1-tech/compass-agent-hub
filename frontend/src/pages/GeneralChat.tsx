import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, X, Cpu, MessageSquare, Zap, BarChart2, CheckSquare, Shield } from 'lucide-react'
import { useAgentStore } from '../stores/agentStore'
import { useWebSocket } from '../hooks/useWebSocket'

interface Message { role: 'user' | 'general' | 'agent'; content: string; name?: string; emoji?: string; ts?: string }
interface ActiveAgent { oc_id: string; name: string; emoji: string; hub_id: string }

const SUGGESTIONS = [
  { Icon: BarChart2,   text: 'Tình hình thế nào?' },
  { Icon: Shield,      text: 'Danh sách tướng lĩnh' },
  { Icon: Zap,         text: 'Chạy Health Check ngay' },
  { Icon: CheckSquare, text: 'Duyệt tất cả pending' },
]

function md(text: string) {
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')
    .replace(/`(.+?)`/g,'<code class="bg-white/10 px-1 rounded text-[11px] font-mono">$1</code>')
    .replace(/\n/g,'<br/>')
}

export default function GeneralChat() {
  const [messages, setMessages]       = useState<Message[]>([])
  const [input, setInput]             = useState('')
  const [loading, setLoading]         = useState(false)
  const [streaming, setStreaming]     = useState('')
  const [activeAgent, setActiveAgent] = useState<ActiveAgent | null>(null)
  const [history, setHistory]         = useState<{ role: string; content: string }[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLTextAreaElement>(null)
  const { agents } = useAgentStore()

  const handleAgentReply = useCallback((data: Record<string, unknown>) => {
    const reply = data as { agent_id: string; name: string; emoji: string; message: string }
    setMessages(m => [...m, {
      role: 'agent', content: reply.message,
      name: reply.name, emoji: reply.emoji,
      ts: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
    }])
    setActiveAgent({ oc_id: reply.agent_id, name: reply.name, emoji: reply.emoji, hub_id: reply.agent_id })
  }, [])
  useWebSocket(handleAgentReply)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, streaming])

  const send = async (msg: string) => {
    if (!msg.trim() || loading) return
    const userMsg = msg.trim()
    const ts      = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    setInput('')
    setLoading(true)
    setMessages(m => [...m, { role: 'user', content: userMsg, ts }])
    const newHistory = [...history, { role: 'user', content: userMsg }]
    setHistory(newHistory)

    try {
      const res = await fetch('/api/general/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: newHistory, active_agent_id: activeAgent?.oc_id ?? '' }),
      })
      const reader  = res.body!.getReader()
      const decoder = new TextDecoder()
      let full = ''
      setStreaming('')

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        for (const line of decoder.decode(value).split('\n')) {
          if (!line.startsWith('data: ')) continue
          const evt = JSON.parse(line.slice(6))
          if (evt.type === 'delta') {
            full += evt.text as string; setStreaming(full)
          } else if (evt.type === 'done') {
            setStreaming('')
            setMessages(m => [...m, { role: 'general', content: full, ts }])
            setHistory(h => [...h, { role: 'assistant', content: full }])
            if (evt.exit_agent)     setActiveAgent(null)
            if (evt.activate_agent) setActiveAgent(evt.activate_agent as ActiveAgent)
          } else if (evt.type === 'error') {
            setStreaming('')
            setMessages(m => [...m, { role: 'general', content: evt.text as string, ts }])
          }
        }
      }
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input) }
  }

  const isScriptAgent = activeAgent
    ? !!agents.find(a => a.openclaw_agent_id === activeAgent.oc_id)?.script
    : false

  return (
    <div className="flex flex-col h-full overflow-hidden bg-bg">

      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-border bg-surface shrink-0">
        <div className="relative">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#7c3aed] to-[#2563eb] flex items-center justify-center">
            <Cpu size={18} className="text-white"/>
          </div>
          <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-green border-2 border-bg"/>
        </div>
        <div>
          <p className="font-bold text-sm text-white">Đại Tướng Nathan-Ubu</p>
          <p className="text-[11px] text-gray-500">Tổng chỉ huy · Nắm toàn bộ đế chế</p>
        </div>
        <div className="ml-auto text-[11px] text-green flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-green animate-pulse"/>Sẵn sàng
        </div>
      </div>

      {/* Active agent banner */}
      {activeAgent && (
        <div className="flex items-center gap-2.5 px-5 py-2 bg-blue/5 border-b border-blue/15 shrink-0">
          <MessageSquare size={12} className="text-blue shrink-0"/>
          <span className="text-xs text-gray-300">
            Đang nói chuyện với{' '}
            <span className="font-semibold text-white">{activeAgent.emoji} {activeAgent.name}</span>
          </span>
          <span className="text-gray-600 text-xs">— nhắn "xong" để thoát</span>
          <button onClick={() => setActiveAgent(null)}
            className="ml-auto p-0.5 text-gray-600 hover:text-red transition-colors rounded">
            <X size={13}/>
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="bg-surface border border-border rounded-2xl p-5 max-w-md">
            <p className="text-sm text-gray-200 font-medium mb-1">Thần Nathan-Ubu kính chào Chủ tướng.</p>
            <p className="text-xs text-gray-500 leading-relaxed">
              Thần nắm toàn bộ thông tin đế chế và sẵn sàng thực thi mệnh lệnh.
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 animate-slide-in ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {m.role !== 'user' && (
              <div className="w-7 h-7 rounded-lg bg-surface2 flex items-center justify-center text-sm shrink-0 mt-0.5">
                {m.role === 'agent' ? m.emoji : <Cpu size={13} className="text-violet"/>}
              </div>
            )}
            <div className="max-w-[72%]">
              {m.role === 'agent' && (
                <p className="text-[10px] text-blue font-semibold mb-1 uppercase tracking-wider">
                  {m.name} báo cáo
                </p>
              )}
              <div className={`px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                m.role === 'user'
                  ? 'bg-blue text-white rounded-br-sm'
                  : 'bg-surface border border-border text-gray-200 rounded-bl-sm'
              }`} dangerouslySetInnerHTML={{ __html: md(m.content) }}/>
              {m.ts && <p className="text-[10px] text-gray-700 mt-0.5 px-1">{m.ts}</p>}
            </div>
          </div>
        ))}

        {streaming && (
          <div className="flex gap-3 justify-start animate-slide-in">
            <div className="w-7 h-7 rounded-lg bg-surface2 flex items-center justify-center shrink-0 mt-0.5">
              <Cpu size={13} className="text-violet"/>
            </div>
            <div className="max-w-[72%] px-3.5 py-2.5 rounded-2xl rounded-bl-sm bg-surface border border-border text-sm text-gray-200 leading-relaxed"
              dangerouslySetInnerHTML={{ __html: md(streaming) }}/>
          </div>
        )}

        {loading && !streaming && (
          <div className="flex gap-3 justify-start">
            <div className="w-7 h-7 rounded-lg bg-surface2 flex items-center justify-center shrink-0">
              <Cpu size={13} className="text-violet"/>
            </div>
            <div className="flex items-center gap-1 px-4 py-3 bg-surface border border-border rounded-2xl rounded-bl-sm">
              {[0,1,2].map(i => (
                <span key={i} className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s`}}/>
              ))}
            </div>
          </div>
        )}
        <div ref={bottomRef}/>
      </div>

      {/* Input */}
      <div className="px-4 pb-4 pt-2 border-t border-border bg-surface shrink-0">
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2.5">
            {SUGGESTIONS.map(s => (
              <button key={s.text} onClick={() => send(s.text)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-full bg-surface2 border border-border text-gray-400 hover:border-blue/40 hover:text-blue transition-colors">
                <s.Icon size={11}/>{s.text}
              </button>
            ))}
          </div>
        )}

        <div className="flex gap-2 items-end">
          <textarea ref={inputRef} value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey} rows={1}
            placeholder={activeAgent ? `Nhắn với ${activeAgent.name}...` : 'Hạ lệnh cho Đại Tướng...'}
            className="flex-1 bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-600 resize-none focus:outline-none focus:border-blue/60 transition-colors"
            style={{ minHeight: 42, maxHeight: 120 }}
            onInput={e => {
              const el = e.currentTarget
              el.style.height = 'auto'
              el.style.height = Math.min(el.scrollHeight, 120) + 'px'
            }}
          />
          <button onClick={() => send(input)} disabled={loading || !input.trim()}
            className="w-10 h-10 rounded-xl bg-blue flex items-center justify-center text-white hover:bg-blue/80 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0">
            <Send size={15}/>
          </button>
        </div>
      </div>
    </div>
  )
}
