import { useState, useRef, useEffect, useCallback } from 'react'
import { useAgentStore } from '../stores/agentStore'
import { useWebSocket } from '../hooks/useWebSocket'

interface Message { role: 'user' | 'general' | 'agent'; content: string; name?: string; emoji?: string }
interface ActiveAgent { oc_id: string; name: string; emoji: string; hub_id: string }

const SUGGESTIONS = [
  { icon: '📊', text: 'Tình hình thế nào?' },
  { icon: '⚔️', text: 'Danh sách tướng' },
  { icon: '🏥', text: 'Chạy Health Check ngay' },
  { icon: '✅', text: 'Duyệt tất cả pending' },
]

function md(text: string) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/`(.+?)`/g, '<code class="bg-white/10 px-1 rounded text-xs">$1</code>')
    .replace(/\n/g, '<br/>')
}

export default function GeneralChat() {
  const [messages, setMessages]     = useState<Message[]>([])
  const [input, setInput]           = useState('')
  const [loading, setLoading]       = useState(false)
  const [streaming, setStreaming]   = useState('')
  const [activeAgent, setActiveAgent] = useState<ActiveAgent | null>(null)
  const [history, setHistory]       = useState<{ role: string; content: string }[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef  = useRef<HTMLTextAreaElement>(null)
  const { agents } = useAgentStore()

  // WebSocket: nhận agent_reply
  const handleAgentReply = useCallback((data: Record<string, unknown>) => {
    const reply = data as { agent_id: string; name: string; emoji: string; message: string }
    setMessages(m => [...m, { role: 'agent', content: reply.message, name: reply.name, emoji: reply.emoji }])
    setActiveAgent({ oc_id: reply.agent_id, name: reply.name, emoji: reply.emoji, hub_id: reply.agent_id })
  }, [])
  useWebSocket(handleAgentReply)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, streaming])

  const send = async (msg: string) => {
    if (!msg.trim() || loading) return
    const userMsg = msg.trim()
    setInput('')
    setLoading(true)
    setMessages(m => [...m, { role: 'user', content: userMsg }])
    const newHistory = [...history, { role: 'user', content: userMsg }]
    setHistory(newHistory)

    try {
      const res = await fetch('/api/general/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
            full += evt.text as string
            setStreaming(full)
          } else if (evt.type === 'done') {
            setStreaming('')
            setMessages(m => [...m, { role: 'general', content: full }])
            setHistory(h => [...h, { role: 'assistant', content: full }])
            if (evt.exit_agent)      setActiveAgent(null)
            if (evt.activate_agent)  setActiveAgent(evt.activate_agent as ActiveAgent)
          } else if (evt.type === 'error') {
            setStreaming('')
            setMessages(m => [...m, { role: 'general', content: evt.text as string }])
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

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-gradient-to-r from-[#1a0a2e] to-surface shrink-0">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-gold to-yellow-600 flex items-center justify-center text-xl">⚔️</div>
        <div>
          <p className="font-bold text-gold text-sm">Đại Tướng Nathan-Ubu</p>
          <p className="text-xs text-gray-400">Tổng chỉ huy · Nắm toàn bộ đế chế</p>
        </div>
        <div className="ml-auto flex items-center gap-1.5 text-xs text-cyan">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan animate-pulse"/>Sẵn sàng
        </div>
      </div>

      {/* Active agent banner */}
      {activeAgent && (
        <div className="flex items-center gap-2 px-4 py-1.5 bg-blue/10 border-b border-blue/20 text-xs text-cyan shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan animate-pulse"/>
          <span>Đang nói chuyện với <b className="text-white">{activeAgent.emoji} {activeAgent.name}</b></span>
          <span className="text-gray-500">— nhắn "xong" để quay lại</span>
          <button onClick={() => setActiveAgent(null)} className="ml-auto text-gray-500 hover:text-red transition-colors">✕</button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 && (
          <div className="bg-surface border border-border rounded-xl p-4 text-sm text-gray-300 max-w-lg">
            <p>⚔️ Thần Nathan-Ubu kính chào Chủ tướng.</p>
            <p className="mt-1 text-gray-400">Thần nắm toàn bộ thông tin đế chế và sẵn sàng thực thi mệnh lệnh.</p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-in`}>
            <div className={`max-w-[75%] ${m.role === 'user' ? '' : ''}`}>
              {(m.role === 'agent') && (
                <p className="text-xs text-cyan font-semibold mb-1">{m.emoji} {m.name} báo cáo:</p>
              )}
              <div
                className={`px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-blue text-white rounded-br-sm'
                    : 'bg-surface border border-border text-gray-200 rounded-bl-sm'
                }`}
                dangerouslySetInnerHTML={{ __html: md(m.content) }}
              />
              <p className="text-xs text-gray-600 mt-0.5 px-1">{new Date().toLocaleTimeString('vi-VN')}</p>
            </div>
          </div>
        ))}

        {/* Streaming */}
        {streaming && (
          <div className="flex justify-start animate-slide-in">
            <div className="max-w-[75%] px-3.5 py-2.5 rounded-2xl rounded-bl-sm bg-surface border border-border text-sm text-gray-200 leading-relaxed"
              dangerouslySetInnerHTML={{ __html: md(streaming) }}
            />
          </div>
        )}

        {/* Loading dots */}
        {loading && !streaming && (
          <div className="flex gap-1 px-4 py-2">
            {[0,1,2].map(i => (
              <span key={i} className="w-2 h-2 rounded-full bg-gray-500 animate-pulse" style={{ animationDelay: `${i * 0.2}s` }}/>
            ))}
          </div>
        )}

        <div ref={bottomRef}/>
      </div>

      {/* Input area */}
      <div className="px-4 pb-4 pt-2 border-t border-border bg-surface shrink-0">
        {/* Suggestions */}
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {SUGGESTIONS.map(s => (
              <button key={s.text} onClick={() => send(s.text)}
                className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-full bg-surface2 border border-border text-gray-400 hover:border-gold hover:text-gold transition-colors">
                <span>{s.icon}</span><span>{s.text}</span>
              </button>
            ))}
          </div>
        )}
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder={activeAgent ? `Nhắn trực tiếp với ${activeAgent.name}...` : 'Hạ lệnh cho Đại Tướng...'}
            rows={1}
            className="flex-1 bg-bg border border-border rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-500 resize-none focus:outline-none focus:border-blue transition-colors"
            style={{ minHeight: 42, maxHeight: 120 }}
            onInput={e => {
              const el = e.currentTarget
              el.style.height = 'auto'
              el.style.height = Math.min(el.scrollHeight, 120) + 'px'
            }}
          />
          <button
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-gold to-yellow-600 text-black font-bold text-sm hover:opacity-90 disabled:opacity-40 transition-opacity shrink-0"
          >
            ⚔️
          </button>
        </div>
      </div>
    </div>
  )
}
