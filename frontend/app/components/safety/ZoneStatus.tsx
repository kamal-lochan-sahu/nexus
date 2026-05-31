'use client'
import { SafetyData } from '../../../hooks/useMockData'

interface Props { data: SafetyData }

export default function ZoneStatus({ data }: Props) {
  const col = (s:string) => s==='CLEAR' ? 'var(--success)' : s==='WARNING' ? 'var(--warning)' : 'var(--danger)'
  const cls = (s:string) => s==='CLEAR' ? 'dot-on' : s==='WARNING' ? 'dot-warn' : 'dot-err'

  return (
    <div className="card" style={{ padding:12 }}>
      <p className="label" style={{ marginBottom:8 }}>SAFETY ZONES — 4 ACTIVE</p>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:6 }}>
        {data.zones.map(z => (
          <div key={z.id} style={{ padding:'8px 10px', background:'var(--bg-secondary)',
            borderRadius:3, border:`1px solid ${col(z.status)}33` }}>
            <div style={{ display:'flex', justifyContent:'space-between', marginBottom:3 }}>
              <span style={{ fontFamily:'var(--font-mono)', fontSize:12, fontWeight:700, color:'var(--text-primary)' }}>{z.id}</span>
              <span className={`dot ${cls(z.status)}`}/>
            </div>
            <p style={{ fontSize:10, color: col(z.status), fontFamily:'var(--font-mono)' }}>{z.status}</p>
            <p style={{ fontSize:10, color:'var(--text-secondary)' }}>{z.dist.toFixed(1)} m</p>
          </div>
        ))}
      </div>
    </div>
  )
}
