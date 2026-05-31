'use client'
import { useState, useEffect, useRef, useCallback } from 'react'

export type WSStatus = 'CONNECTING'|'CONNECTED'|'DISCONNECTED'|'ERROR'

export function useWebSocket(url: string) {
  const [status, setStatus]   = useState<WSStatus>('CONNECTING')
  const [lastMsg, setLastMsg] = useState<string|null>(null)
  const ws  = useRef<WebSocket|null>(null)
  const tmr = useRef<ReturnType<typeof setTimeout>|null>(null)
  const alive = useRef(true)

  const connect = useCallback(() => {
    if (!alive.current) return
    try {
      const sock = new WebSocket(url)
      ws.current = sock
      sock.onopen    = () => alive.current && setStatus('CONNECTED')
      sock.onmessage = e  => alive.current && setLastMsg(e.data)
      sock.onclose   = () => { if (alive.current) { setStatus('DISCONNECTED'); tmr.current = setTimeout(connect, 3000) } }
      sock.onerror   = () => { setStatus('ERROR'); sock.close() }
    } catch {
      if (alive.current) { setStatus('DISCONNECTED'); tmr.current = setTimeout(connect, 5000) }
    }
  }, [url])

  useEffect(() => {
    alive.current = true
    connect()
    return () => { alive.current = false; tmr.current && clearTimeout(tmr.current); ws.current?.close() }
  }, [connect])

  const send = useCallback((msg: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(msg)
  }, [])

  return { status, lastMsg, send }
}
