'use client'
import { FleetData } from '../../../hooks/useMockData'

interface Props { logs: FleetData['coordLogs'] }

export default function CoordLog({ logs }: Props) {
  return (
    <div className="card" style={{ padding:12, flex:1 }}>
      <p className="label" style={{ marginBottom:8 }}>COORD LOG</p>
      {[...logs].reverse().map((l, i) => (
        <div key={i} style={{ display:'flex', gap:8, marginBottom:5, fontSize:10 }}>
          <span style={{ color:'var(--text-secondary)', fontFamily:'var(--font-mono)', flexShrink:0 }}>
            {new Date(l.ts).toLocaleTimeString('en-GB')}
          </span>
          <span style={{ color:'var(--accent-cyan)', fontFamily:'var(--font-mono)' }}>{l.msg}</span>
        </div>
      ))}
    </div>
  )
}
