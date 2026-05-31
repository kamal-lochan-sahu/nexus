'use client'
import { TwinData } from '../../../hooks/useMockData'

interface Props { data: TwinData }

export default function Robot3D({ data }: Props) {
  const j = data.joints  // 12 values

  // Top-down SVG quadruped — body + 4 legs (each 3 joints)
  const legPoints = (bx:number, by:number, angle:number, j1:number, j2:number) => {
    const rad = (a:number) => (a * Math.PI) / 180
    const x1 = bx + Math.cos(rad(angle)) * 22
    const y1 = by + Math.sin(rad(angle)) * 22
    const x2 = x1 + Math.cos(rad(angle + j1*0.5)) * 20
    const y2 = y1 + Math.sin(rad(angle + j1*0.5)) * 20
    const x3 = x2 + Math.cos(rad(angle + j2*0.4)) * 18
    const y3 = y2 + Math.sin(rad(angle + j2*0.4)) * 18
    return { hip:[bx,by], knee:[x1,y1], ankle:[x2,y2], foot:[x3,y3] }
  }

  const cx=130, cy=130
  const legs = [
    legPoints(cx-28, cy-20, -140, j[0], j[1]),   // FL
    legPoints(cx+28, cy-20,  -40, j[3], j[4]),    // FR
    legPoints(cx-28, cy+20,  140, j[6], j[7]),    // RL
    legPoints(cx+28, cy+20,   40, j[9], j[10]),   // RR
  ]

  const healthColor = data.health > 90 ? 'var(--success)' : data.health > 75 ? 'var(--warning)' : 'var(--danger)'

  return (
    <div className="card factory-grid" style={{ padding:14, display:'flex', flexDirection:'column' }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:8 }}>
        <p className="label">UNITREE GO2 — DIGITAL TWIN</p>
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <span className="dot dot-on"/>
          <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color:'var(--success)' }}>LIVE</span>
        </div>
      </div>
      <svg viewBox="0 0 260 260" style={{ flex:1, display:'block', width:'100%' }}>
        {/* Legs */}
        {legs.map((leg, li) => (
          <g key={li}>
            <line x1={leg.hip[0]}   y1={leg.hip[1]}   x2={leg.knee[0]}  y2={leg.knee[1]}
              stroke="var(--accent-purple)" strokeWidth="3" strokeLinecap="round"/>
            <line x1={leg.knee[0]}  y1={leg.knee[1]}  x2={leg.ankle[0]} y2={leg.ankle[1]}
              stroke="var(--accent-cyan)" strokeWidth="2.5" strokeLinecap="round"/>
            <line x1={leg.ankle[0]} y1={leg.ankle[1]} x2={leg.foot[0]}  y2={leg.foot[1]}
              stroke="var(--accent-cyan)" strokeWidth="2" strokeLinecap="round" opacity=".7"/>
            <circle cx={leg.knee[0]}  cy={leg.knee[1]}  r="3" fill="var(--accent-purple)"/>
            <circle cx={leg.ankle[0]} cy={leg.ankle[1]} r="2.5" fill="var(--accent-cyan)" opacity=".8"/>
            <circle cx={leg.foot[0]}  cy={leg.foot[1]}  r="2" fill="var(--text-secondary)"/>
          </g>
        ))}
        {/* Body */}
        <rect x={cx-30} y={cy-18} width="60" height="36" rx="6"
          fill="var(--bg-card)" stroke="var(--accent-cyan)" strokeWidth="1.5"/>
        {/* Head */}
        <rect x={cx-14} y={cy-30} width="28" height="16" rx="4"
          fill="var(--bg-card)" stroke="var(--accent-purple)" strokeWidth="1.5"/>
        {/* Eyes */}
        <circle cx={cx-5}  cy={cy-23} r="3" fill="var(--accent-cyan)" opacity=".9"/>
        <circle cx={cx+5}  cy={cy-23} r="3" fill="var(--accent-cyan)" opacity=".9"/>
        {/* Spine indicators */}
        {[-12,-4,4,12].map(x => (
          <circle key={x} cx={cx+x} cy={cy} r="2" fill="var(--accent-purple)" opacity=".7"/>
        ))}
        {/* Health overlay */}
        <text x={cx} y={cy+9} textAnchor="middle"
          fill={healthColor} fontSize="9" fontFamily="monospace" fontWeight="700">
          {data.health.toFixed(0)}%
        </text>
      </svg>
      {/* Joint values */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:3, marginTop:8 }}>
        {['FL','FR','RL','RR'].map((leg,li) => (
          <div key={leg} style={{ padding:'4px 6px', background:'var(--bg-secondary)',
            borderRadius:2, textAlign:'center' }}>
            <p style={{ fontSize:9, color:'var(--text-secondary)' }}>{leg}</p>
            <p style={{ fontFamily:'var(--font-mono)', fontSize:10, color:'var(--accent-cyan)' }}>
              {(j[li*3]||0).toFixed(0)}°
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
