'use client'
import { VisionData } from '../../../hooks/useMockData'

interface Props { data: VisionData }

export default function DetectionPanel({ data }: Props) {
  return (
    <div className="card" style={{ padding:12 }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:8 }}>
        <p className="label">DETECTIONS</p>
        <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color:'var(--accent-cyan)' }}>
          YOLOv8
        </span>
      </div>
      {data.detections.map(d => (
        <div key={d.id} style={{ display:'flex', alignItems:'center', gap:8, marginBottom:8,
          padding:'6px 8px', background:'var(--bg-secondary)', borderRadius:2 }}>
          <div style={{ width:28, height:28, background:'rgba(0,212,255,.1)',
            border:'1px solid var(--accent-cyan)', borderRadius:2,
            display:'flex', alignItems:'center', justifyContent:'center',
            fontSize:10, color:'var(--accent-cyan)' }}>
            {d.id}
          </div>
          <div style={{ flex:1 }}>
            <p style={{ fontFamily:'var(--font-mono)', fontSize:11, color:'var(--text-primary)', fontWeight:600 }}>
              {d.label}
            </p>
            <div style={{ display:'flex', gap:6, marginTop:3 }}>
              <span style={{ fontSize:9, color:'var(--text-secondary)' }}>
                {d.bbox[2]}×{d.bbox[3]}px
              </span>
            </div>
          </div>
          <div style={{ textAlign:'right' }}>
            <p style={{ fontFamily:'var(--font-mono)', fontSize:12, fontWeight:700,
              color: d.conf > 0.9 ? 'var(--success)' : 'var(--warning)' }}>
              {(d.conf*100).toFixed(0)}%
            </p>
          </div>
        </div>
      ))}
      {data.detections.length === 0 && (
        <p style={{ color:'var(--text-secondary)', fontSize:11, fontFamily:'var(--font-mono)' }}>
          No objects detected
        </p>
      )}
    </div>
  )
}
