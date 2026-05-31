'use client'
import { useState, useRef, useEffect } from 'react'
import { LogEntry } from '../../../hooks/useMockData'

interface Props { logs: LogEntry[] }

const MODULES = ['ALL','SYSTEM','NL2RC','TWIN','SAFETY','RL','FLEET','VLA','WS']
const COLOR: Record<string,string> = {
  SUCCESS: 'var(--success)', INFO: 'var(--accent-cyan)',
  WARNING: 'var(--warning)', ERROR: 'var(--danger)',
}

export default function Terminal({ logs }: Props) {
  const [filter, setFilter]   = useState('ALL')
  const [paused, setPaused]   = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const visible = filter === 'ALL' ? logs : logs.filter(l => l.module === filter)

  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior:'smooth' })
  }, [logs, paused])

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', padding:12, gap:8 }}>
      {/* Toolbar */}
      <div style={{ display:'flex', alignItems:'center', gap:10, flexShrink:0 }}>
        <span style={{ fontFamily:'var(--font-mono)', fontSize:12, color:'var(--accent-cyan)' }}>
          ▶ NEXUS LOG STREAM
        </span>
        <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color:'var(--text-secondary)' }}>
          {visible.length} lines
        </span>
        <div style={{ flex:1 }}/>
        <select value={filter} onChange={e => setFilter(e.target.value)}
          style={{ background:'var(--bg-secondary)', border:'1px solid var(--border)',
            color:'var(--text-secondary)', borderRadius:3, padding:'4px 8px',
            fontFamily:'var(--font-mono)', fontSize:11, cursor:'pointer' }}>
          {MODULES.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <button onClick={() => setPaused(p => !p)}
          style={{ padding:'4px 10px', background: paused ? 'var(--warning)' : 'var(--bg-secondary)',
            border:'1px solid var(--border)', borderRadius:3, color: paused ? '#000' : 'var(--text-secondary)',
            fontFamily:'var(--font-mono)', fontSize:11, cursor:'pointer', fontWeight: paused ? 700 : 400 }}>
          {paused ? 'RESUME' : 'PAUSE'}
        </button>
      </div>

      {/* Log area */}
      <div className="card" style={{ flex:1, overflow:'auto', padding:'10px 14px',
        background:'var(--bg-secondary)', fontFamily:'var(--font-mono)', fontSize:12 }}>
        {visible.map(l => (
          <div key={l.id} style={{ display:'flex', gap:10, lineHeight:1.7 }}>
            <span style={{ color:'var(--text-secondary)', flexShrink:0, fontSize:10 }}>
              {new Date(l.ts).toLocaleTimeString('en-GB')}
            </span>
            <span style={{ color: COLOR[l.level] || 'var(--text-secondary)', flexShrink:0, width:56, fontSize:10 }}>
              [{l.level}]
            </span>
            <span style={{ color:'var(--accent-purple)', flexShrink:0, width:58, fontSize:10 }}>
              {l.module}
            </span>
            <span style={{ color:'var(--text-primary)', fontSize:11 }}>{l.msg}</span>
          </div>
        ))}
        <div ref={bottomRef}/>
      </div>
    </div>
  )
}
