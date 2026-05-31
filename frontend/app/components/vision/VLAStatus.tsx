'use client'
import { VisionData } from '../../../hooks/useMockData'

interface Props { data: VisionData }

const PIPELINE = [
  {label:'CLIP', sub:'Vision encoder'},
  {label:'YOLOv8', sub:'Object detect'},
  {label:'Groq LLM', sub:'Llama-3.1-8b'},
  {label:'Action', sub:'Go2 dispatch'},
]

export default function VLAStatus({ data }: Props) {
  return (
    <div className="card" style={{ padding:12, flex:1 }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:10 }}>
        <p className="label">VLA PIPELINE</p>
        <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color:'var(--success)' }}>
          {data.vlaStatus}
        </span>
      </div>

      {/* Pipeline steps */}
      <div style={{ display:'flex', alignItems:'center', gap:0, marginBottom:10 }}>
        {PIPELINE.map((p, i) => (
          <div key={p.label} style={{ display:'flex', alignItems:'center', flex:1 }}>
            <div style={{ flex:1, textAlign:'center' }}>
              <div style={{ padding:'4px 6px', background:'rgba(0,212,255,.08)',
                border:'1px solid var(--accent-cyan)', borderRadius:2, marginBottom:2 }}>
                <p style={{ fontFamily:'var(--font-mono)', fontSize:10, color:'var(--accent-cyan)', fontWeight:700 }}>
                  {p.label}
                </p>
                <p style={{ fontSize:8, color:'var(--text-secondary)' }}>{p.sub}</p>
              </div>
              <span className="dot dot-on" style={{ margin:'0 auto', display:'block', width:5, height:5 }}/>
            </div>
            {i < PIPELINE.length - 1 && (
              <div style={{ width:8, height:1, background:'var(--accent-cyan)', opacity:.5 }}/>
            )}
          </div>
        ))}
      </div>

      {/* Latency */}
      <div style={{ padding:'8px', background:'var(--bg-secondary)', borderRadius:3, textAlign:'center' }}>
        <p style={{ fontSize:9, color:'var(--text-secondary)', marginBottom:3 }}>END-TO-END LATENCY</p>
        <p style={{ fontFamily:'var(--font-mono)', fontSize:'1.4rem', fontWeight:700, color:'var(--accent-cyan)', lineHeight:1 }}>
          {data.vlaLatency.toFixed(1)}s
        </p>
      </div>
    </div>
  )
}
