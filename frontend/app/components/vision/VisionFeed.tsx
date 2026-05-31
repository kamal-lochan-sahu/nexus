'use client'
import { VisionData } from '../../../hooks/useMockData'

interface Props { data: VisionData }

export default function VisionFeed({ data }: Props) {
  return (
    <div className="card" style={{ display:'flex', flexDirection:'column', overflow:'hidden' }}>
      <div style={{ display:'flex', justifyContent:'space-between', padding:'10px 12px',
        borderBottom:'1px solid var(--border)', flexShrink:0 }}>
        <p className="label">VISION FEED — EmbodiedGPT</p>
        <div style={{ display:'flex', gap:10 }}>
          <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color:'var(--accent-cyan)' }}>
            {data.fps}fps
          </span>
          <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color:'var(--success)' }}>
            {data.detections.length} objects
          </span>
        </div>
      </div>

      {/* Mock camera area */}
      <div className="factory-grid" style={{ flex:1, position:'relative', background:'#060A14', minHeight:180 }}>
        {/* Scan line */}
        <div style={{ position:'absolute', left:0, right:0, height:1,
          background:'linear-gradient(90deg,transparent,var(--success),transparent)',
          animation:'scan 2s linear infinite', opacity:.5 }}/>

        {/* Detection boxes */}
        {data.detections.map(d => (
          <div key={d.id} style={{
            position:'absolute',
            left:`${(d.bbox[0]/480)*100}%`, top:`${(d.bbox[1]/320)*100}%`,
            width:`${(d.bbox[2]/480)*100}%`, height:`${(d.bbox[3]/320)*100}%`,
            border:'1.5px solid var(--accent-cyan)', borderRadius:2,
          }}>
            <span style={{ position:'absolute', top:-16, left:0, fontSize:9,
              background:'var(--accent-cyan)', color:'#000',
              padding:'1px 4px', fontFamily:'monospace', fontWeight:700, whiteSpace:'nowrap' }}>
              {d.label} {(d.conf*100).toFixed(0)}%
            </span>
          </div>
        ))}

        {/* CLIP feature map visualization */}
        <div style={{ position:'absolute', right:8, bottom:8, display:'grid',
          gridTemplateColumns:'repeat(8,1fr)', gap:1, opacity:.4 }}>
          {Array.from({length:32}).map((_,i) => (
            <div key={i} style={{ width:6, height:6,
              background:`hsl(${190 + (i*7)%60}, 80%, ${30+Math.sin(i)*20}%)`,
              borderRadius:1 }}/>
          ))}
        </div>

        <div style={{ position:'absolute', bottom:8, left:8, fontFamily:'var(--font-mono)',
          fontSize:10, color:'var(--success)' }}>
          CLIP+YOLOv8 · {data.vlaLatency.toFixed(1)}s pipeline
        </div>
      </div>
    </div>
  )
}
