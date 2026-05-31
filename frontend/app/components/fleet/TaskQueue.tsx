'use client'
import { FleetData } from '../../../hooks/useMockData'

interface Props { tasks: FleetData['tasks'] }

const ST_COLOR: Record<string,string> = {
  ACTIVE:'var(--success)', QUEUED:'var(--warning)', DONE:'var(--text-secondary)', FAILED:'var(--danger)'
}

export default function TaskQueue({ tasks }: Props) {
  return (
    <div className="card" style={{ padding:12 }}>
      <p className="label" style={{ marginBottom:8 }}>TASK QUEUE ({tasks.length})</p>
      {tasks.map(t => (
        <div key={t.id} style={{ marginBottom:8 }}>
          <div style={{ display:'flex', justifyContent:'space-between', marginBottom:3 }}>
            <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color:'var(--text-primary)' }}>
              {t.id} · {t.type}
            </span>
            <span style={{ fontSize:9, color: ST_COLOR[t.status]||'var(--text-secondary)',
              fontFamily:'var(--font-mono)' }}>
              {t.status}
            </span>
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:6 }}>
            <div style={{ flex:1, height:3, background:'var(--border)', borderRadius:1 }}>
              <div style={{ width:`${t.progress}%`, height:'100%',
                background: ST_COLOR[t.status]||'var(--accent-cyan)',
                borderRadius:1, transition:'width .5s ease' }}/>
            </div>
            <span style={{ fontSize:9, color:'var(--text-secondary)', fontFamily:'var(--font-mono)', width:28, textAlign:'right' }}>
              {t.progress}%
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}
