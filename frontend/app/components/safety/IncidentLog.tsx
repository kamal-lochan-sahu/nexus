'use client'
import { SafetyData } from '../../../hooks/useMockData'

interface Props { data: SafetyData }

export default function IncidentLog({ data }: Props) {
  return (
    <div className="card" style={{ padding:12, flex:1, overflow:'hidden', display:'flex', flexDirection:'column' }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:8 }}>
        <p className="label">INCIDENT LOG</p>
        <span style={{ fontFamily:'var(--font-mono)', fontSize:10,
          color: data.incidents === 0 ? 'var(--success)' : 'var(--danger)' }}>
          {data.incidents} incidents
        </span>
      </div>
      {data.incidents === 0 ? (
        <div style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center',
          justifyContent:'center', gap:6 }}>
          <span style={{ fontSize:24 }}>✓</span>
          <p style={{ fontFamily:'var(--font-mono)', fontSize:11, color:'var(--success)', letterSpacing:'.1em' }}>
            ALL CLEAR
          </p>
          <p style={{ fontSize:10, color:'var(--text-secondary)' }}>No safety incidents recorded</p>
        </div>
      ) : (
        <div style={{ flex:1, overflow:'auto' }}>
          {/* Would render incidents if any */}
        </div>
      )}
    </div>
  )
}
