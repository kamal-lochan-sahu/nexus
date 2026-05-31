'use client'
import { MockData } from '../../../hooks/useMockData'

interface Props { data: MockData }

const MODULES = [
  { id:'NL2RC',       label:'NL2RC',        sub:'Groq LLM → Go2',         status:'ONLINE' },
  { id:'TWIN',        label:'CognitiveTwin',sub:'LSTM Failure Pred',       status:'ONLINE' },
  { id:'SAFETY',      label:'CoboSense',    sub:'ISO/TS 15066 HRC',        status:'ONLINE' },
  { id:'RL',          label:'RoboRL',       sub:'PPO Navigation',          status:'ONLINE' },
  { id:'FLEET',       label:'FlexCell',     sub:'Multi-Robot Coord',       status:'ONLINE' },
  { id:'VLA',         label:'EmbodiedGPT',  sub:'VLA Pipeline 2.3s',       status:'ONLINE' },
]

export default function Overview({ data }: Props) {
  const { kpis, fleet } = data
  const kpiCards = [
    { label:'Units Assembled', val: kpis.units,    unit:'',  color:'var(--accent-cyan)' },
    { label:'Safety Incidents',val: kpis.incidents, unit:'', color:'var(--success)' },
    { label:'Twin Health',     val: kpis.health.toFixed(1), unit:'%', color:'var(--accent-cyan)' },
    { label:'RL Nav SR',       val: kpis.sr,        unit:'%', color:'var(--success)' },
  ]

  // Simple factory SVG: 6×6 m floor
  const scale = 40  // px per meter
  const go2a = fleet.go2a.pos
  const go2b = fleet.go2b.pos

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:12, padding:12, height:'100%', overflow:'auto' }}>

      {/* KPI Bar */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:10 }}>
        {kpiCards.map(k => (
          <div key={k.label} className="card" style={{ padding:14 }}>
            <p className="label" style={{ marginBottom:6 }}>{k.label}</p>
            <p style={{ fontFamily:'var(--font-mono)', fontSize:'1.6rem', fontWeight:700, color:k.color, lineHeight:1 }}>
              {k.val}<span style={{ fontSize:'0.9rem', marginLeft:2 }}>{k.unit}</span>
            </p>
          </div>
        ))}
      </div>

      {/* Main row: factory map + module grid */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, flex:1 }}>

        {/* Factory map SVG */}
        <div className="card factory-grid" style={{ padding:12, position:'relative', overflow:'hidden' }}>
          <p className="label" style={{ marginBottom:8 }}>FACTORY FLOOR — 6×6 m</p>
          <svg width="100%" viewBox="0 0 260 260" style={{ display:'block' }}>
            {/* Floor border */}
            <rect x="10" y="10" width="240" height="240" fill="none"
              stroke="var(--border)" strokeWidth="1.5"/>
            {/* 4 zones */}
            {[
              {x:10,y:10,label:'Z1'},{x:130,y:10,label:'Z2'},
              {x:10,y:130,label:'Z3'},{x:130,y:130,label:'Z4'},
            ].map(z => (
              <g key={z.label}>
                <rect x={z.x} y={z.y} width="120" height="120" fill="none"
                  stroke="rgba(30,45,79,.8)" strokeWidth="1" strokeDasharray="4,4"/>
                <text x={z.x+6} y={z.y+14} fill="var(--text-secondary)" fontSize="9"
                  fontFamily="monospace">{z.label}</text>
              </g>
            ))}
            {/* Charging station */}
            <rect x="112" y="112" width="36" height="36" rx="3"
              fill="rgba(124,58,237,.15)" stroke="var(--accent-purple)" strokeWidth="1"/>
            <text x="130" y="134" textAnchor="middle" fill="var(--accent-purple)" fontSize="8" fontFamily="monospace">BASE</text>
            {/* Go2-A */}
            <circle cx={10 + go2a.x * scale} cy={10 + go2a.y * scale} r="7"
              fill="var(--accent-cyan)" opacity=".9"/>
            <text x={10 + go2a.x*scale} y={10 + go2a.y*scale - 10}
              textAnchor="middle" fill="var(--accent-cyan)" fontSize="8" fontFamily="monospace">A</text>
            {/* Go2-B */}
            <circle cx={10 + go2b.x * scale} cy={10 + go2b.y * scale} r="7"
              fill="var(--accent-purple)" opacity=".9"/>
            <text x={10 + go2b.x*scale} y={10 + go2b.y*scale - 10}
              textAnchor="middle" fill="var(--accent-purple)" fontSize="8" fontFamily="monospace">B</text>
          </svg>
        </div>

        {/* Module status grid */}
        <div className="card" style={{ padding:12 }}>
          <p className="label" style={{ marginBottom:8 }}>MODULE STATUS — 6/6 ONLINE</p>
          <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
            {MODULES.map(m => (
              <div key={m.id} style={{ display:'flex', alignItems:'center', justifyContent:'space-between',
                padding:'8px 10px', background:'var(--bg-secondary)',
                borderRadius:3, border:'1px solid var(--border)' }}>
                <div>
                  <p style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)', fontFamily:'var(--font-mono)' }}>{m.label}</p>
                  <p style={{ fontSize:10, color:'var(--text-secondary)' }}>{m.sub}</p>
                </div>
                <div style={{ display:'flex', alignItems:'center', gap:5 }}>
                  <span style={{ fontSize:10, color:'var(--success)', fontFamily:'var(--font-mono)' }}>ONLINE</span>
                  <span className="dot dot-on"/>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
