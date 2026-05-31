'use client'
import { FleetData } from '../../../hooks/useMockData'

interface Props { data: FleetData }

const W = 280, H = 240, PAD = 20, SCALE = 38  // scale: px per meter

export default function FleetMap({ data }: Props) {
  const toSvg = (x:number, y:number) => ({ cx: PAD + x*SCALE, cy: PAD + y*SCALE })
  const posA = toSvg(data.go2a.pos.x, data.go2a.pos.y)
  const posB = toSvg(data.go2b.pos.x, data.go2b.pos.y)
  const sep  = Math.sqrt((data.go2a.pos.x-data.go2b.pos.x)**2 + (data.go2a.pos.y-data.go2b.pos.y)**2)

  return (
    <div className="card factory-grid" style={{ display:'flex', flexDirection:'column', overflow:'hidden' }}>
      <div style={{ display:'flex', justifyContent:'space-between', padding:'10px 12px',
        borderBottom:'1px solid var(--border)', flexShrink:0 }}>
        <p className="label">FLEET MAP — 6×6 m FACTORY FLOOR</p>
        <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color:'var(--text-secondary)' }}>
          Separation: {sep.toFixed(1)}m
        </span>
      </div>
      <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', padding:12 }}>
        <svg width="100%" viewBox={`0 0 ${W} ${H}`}>
          {/* Floor border */}
          <rect x={PAD} y={PAD} width={W-PAD*2} height={H-PAD*2}
            fill="none" stroke="var(--border)" strokeWidth="1.5"/>

          {/* Zone dividers */}
          <line x1={W/2} y1={PAD} x2={W/2} y2={H-PAD}
            stroke="var(--border)" strokeWidth="1" strokeDasharray="4,4"/>
          <line x1={PAD} y1={H/2} x2={W-PAD} y2={H/2}
            stroke="var(--border)" strokeWidth="1" strokeDasharray="4,4"/>

          {/* Zone labels */}
          {[['Z1',PAD+8,PAD+14],['Z2',W/2+8,PAD+14],['Z3',PAD+8,H/2+14],['Z4',W/2+8,H/2+14]].map(([l,x,y]) => (
            <text key={l as string} x={x as number} y={y as number}
              fill="var(--text-secondary)" fontSize="9" fontFamily="monospace">{l}</text>
          ))}

          {/* Base station */}
          <rect x={W/2-15} y={H/2-12} width="30" height="24" rx="3"
            fill="rgba(124,58,237,.15)" stroke="var(--accent-purple)" strokeWidth="1"/>
          <text x={W/2} y={H/2+4} textAnchor="middle"
            fill="var(--accent-purple)" fontSize="7" fontFamily="monospace">BASE</text>

          {/* Go2-A trail */}
          <circle cx={posA.cx} cy={posA.cy} r="14" fill="rgba(0,212,255,.06)" stroke="none"/>

          {/* Separation line */}
          <line x1={posA.cx} y1={posA.cy} x2={posB.cx} y2={posB.cy}
            stroke="var(--border)" strokeWidth="1" strokeDasharray="3,3"/>
          <text x={(posA.cx+posB.cx)/2} y={(posA.cy+posB.cy)/2 - 4}
            textAnchor="middle" fill="var(--text-secondary)" fontSize="8" fontFamily="monospace">
            {sep.toFixed(1)}m
          </text>

          {/* Go2-A */}
          <circle cx={posA.cx} cy={posA.cy} r="9" fill="var(--accent-cyan)" opacity=".9"/>
          <text x={posA.cx} y={posA.cy+4} textAnchor="middle"
            fill="#000" fontSize="8" fontFamily="monospace" fontWeight="700">A</text>
          <text x={posA.cx} y={posA.cy-14} textAnchor="middle"
            fill="var(--accent-cyan)" fontSize="8" fontFamily="monospace">
            {data.go2a.status}
          </text>

          {/* Go2-B */}
          <circle cx={posB.cx} cy={posB.cy} r="9" fill="var(--accent-purple)" opacity=".9"/>
          <text x={posB.cx} y={posB.cy+4} textAnchor="middle"
            fill="#fff" fontSize="8" fontFamily="monospace" fontWeight="700">B</text>
          <text x={posB.cx} y={posB.cy-14} textAnchor="middle"
            fill="var(--accent-purple)" fontSize="8" fontFamily="monospace">
            {data.go2b.status}
          </text>
        </svg>
      </div>
    </div>
  )
}
