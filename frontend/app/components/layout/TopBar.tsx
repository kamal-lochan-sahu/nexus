'use client'
import { useRef } from 'react'

interface Props { wsStatus: string; uptime: number }

function fmt(s: number) {
  const h = String(Math.floor(s/3600)).padStart(2,'0')
  const m = String(Math.floor((s%3600)/60)).padStart(2,'0')
  const sec = String(s%60).padStart(2,'0')
  return `${h}:${m}:${sec}`
}

const S = {
  bar:   { height:48, background:'var(--bg-secondary)', borderBottom:'1px solid var(--border)',
            display:'flex', alignItems:'center', padding:'0 16px', gap:16, flexShrink:0 },
  logo:  { display:'flex', alignItems:'center', gap:8 },
  name:  { fontFamily:'var(--font-mono)', fontSize:15, fontWeight:700, color:'var(--accent-cyan)', letterSpacing:'.15em' },
  ver:   { fontFamily:'var(--font-mono)', fontSize:10, color:'var(--text-secondary)', letterSpacing:'.08em' },
  pill:  { display:'flex', alignItems:'center', gap:6 },
  lbl:   { fontFamily:'var(--font-mono)', fontSize:10, color:'var(--text-secondary)', letterSpacing:'.08em' },
  clock: { fontFamily:'var(--font-mono)', fontSize:13, color:'var(--text-primary)', letterSpacing:'.12em' },
  div:   { width:1, height:24, background:'var(--border)' },
  space: { flex:1 },
} as const

export default function TopBar({ wsStatus, uptime }: Props) {
  const wsColor = wsStatus === 'CONNECTED' ? 'var(--success)' : wsStatus === 'MOCK' ? 'var(--warning)' : 'var(--danger)'
  const wsLabel = wsStatus === 'CONNECTED' ? 'LIVE' : wsStatus === 'MOCK' ? 'DEMO' : 'OFFLINE'
  const dotCls  = wsStatus === 'MOCK' ? 'dot dot-warn' : 'dot dot-on'

  return (
    <header style={S.bar}>
      <div style={S.logo}>
        <svg width="26" height="26" viewBox="0 0 26 26">
          <polygon points="13,2 22,7.5 22,18.5 13,24 4,18.5 4,7.5"
            fill="none" stroke="var(--accent-cyan)" strokeWidth="1.5"/>
          <text x="13" y="17.5" textAnchor="middle"
            fill="var(--accent-cyan)" fontSize="9" fontFamily="monospace" fontWeight="700">N</text>
        </svg>
        <span style={S.name}>NEXUS</span>
        <span style={S.ver}>v7.0 · INDUSTRY 5.0</span>
      </div>

      <div style={S.space}/>

      <div style={S.pill}>
        <span className="dot dot-on"/>
        <span style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--success)',letterSpacing:'.08em'}}>
          SYSTEM ONLINE
        </span>
      </div>

      <div style={S.div}/>

      <div style={S.pill}>
        <span style={S.lbl}>UPTIME</span>
        <span style={S.clock}>{fmt(uptime)}</span>
      </div>

      <div style={S.div}/>

      <div style={S.pill}>
        <span style={S.lbl}>WS</span>
        <span style={{...S.lbl, color:wsColor, letterSpacing:'.1em'}}>{wsLabel}</span>
        <span className={dotCls}/>
      </div>
    </header>
  )
}
