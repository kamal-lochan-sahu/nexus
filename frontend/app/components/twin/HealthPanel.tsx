'use client'
import { TwinData } from '../../../hooks/useMockData'

interface Props { data: TwinData }

function Bar({ val, max=100, color='var(--accent-cyan)' }: {val:number;max?:number;color?:string}) {
  return (
    <div style={{ height:4, background:'var(--border)', borderRadius:2, overflow:'hidden' }}>
      <div style={{ width:`${(val/max)*100}%`, height:'100%', background:color,
        borderRadius:2, transition:'width .5s ease' }}/>
    </div>
  )
}

export default function HealthPanel({ data }: Props) {
  const healthColor = data.health > 90 ? 'var(--success)' : data.health > 75 ? 'var(--warning)' : 'var(--danger)'
  const batColor    = data.battery > 50 ? 'var(--success)' : data.battery > 25 ? 'var(--warning)' : 'var(--danger)'

  return (
    <div className="card" style={{ padding:14, flex:1 }}>
      <p className="label" style={{ marginBottom:10 }}>ROBOT HEALTH</p>

      {/* Health % */}
      <div style={{ textAlign:'center', padding:'10px 0', marginBottom:10,
        background:'var(--bg-secondary)', borderRadius:3 }}>
        <p style={{ fontFamily:'var(--font-mono)', fontSize:'2.2rem', fontWeight:700, color:healthColor, lineHeight:1 }}>
          {data.health.toFixed(1)}%
        </p>
        <p style={{ fontSize:10, color:'var(--text-secondary)', marginTop:4, letterSpacing:'.08em' }}>SYSTEM HEALTH</p>
      </div>

      {/* Metrics */}
      {[
        { label:'Battery', val:`${data.battery.toFixed(0)}%`,   bar:data.battery, color:batColor },
        { label:'Temp',    val:`${data.temp.toFixed(1)}°C`,      bar:(data.temp/80)*100, color:'var(--warning)' },
        { label:'Anomaly', val:data.anomaly.toFixed(3),          bar:data.anomaly*100,   color:'var(--accent-cyan)' },
      ].map(m => (
        <div key={m.label} style={{ marginBottom:10 }}>
          <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
            <span style={{ fontSize:10, color:'var(--text-secondary)' }}>{m.label}</span>
            <span style={{ fontFamily:'var(--font-mono)', fontSize:11, color:m.color }}>{m.val}</span>
          </div>
          <Bar val={m.bar} color={m.color}/>
        </div>
      ))}

      <p style={{ fontSize:10, color:'var(--text-secondary)', fontFamily:'var(--font-mono)', marginTop:6 }}>
        Uptime: {Math.floor(data.uptimeSec/60)}m {data.uptimeSec%60}s
      </p>
    </div>
  )
}
