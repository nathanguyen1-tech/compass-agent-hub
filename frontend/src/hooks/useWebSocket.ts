import { useEffect, useRef, useCallback } from 'react'
import { useAgentStore } from '../stores/agentStore'
import type { ActivityEvent } from '../types'

type WsHandler = (data: Record<string, unknown>) => void

export function useWebSocket(onAgentReply?: WsHandler) {
  const ws = useRef<WebSocket | null>(null)
  const { addEvent, setConnected, updateAgentStatus } = useAgentStore()

  const connect = useCallback(() => {
    const url = `ws://${location.host}/ws/activity/stream`
    ws.current = new WebSocket(url)

    ws.current.onopen = () => setConnected(true)
    ws.current.onclose = () => {
      setConnected(false)
      setTimeout(connect, 3000)
    }
    ws.current.onerror = () => ws.current?.close()

    ws.current.onmessage = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data as string) as Record<string, unknown>
        if (data.type === 'activity') {
          addEvent(data.event as ActivityEvent)
          const evt = data.event as ActivityEvent
          if (evt.level === 'success') updateAgentStatus(evt.agent_id, 'idle')
          if (evt.level === 'error')   updateAgentStatus(evt.agent_id, 'error')
        }
        if (data.type === 'agent_reply' && onAgentReply) {
          onAgentReply(data)
        }
      } catch { /* ignore */ }
    }
  }, [addEvent, setConnected, updateAgentStatus, onAgentReply])

  useEffect(() => { connect(); return () => ws.current?.close() }, [connect])

  return ws
}
