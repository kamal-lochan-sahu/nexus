'use client'
import { RobotData } from '../../../hooks/useMockData'

interface Props { robot: RobotData; name: string }

const STATUS_COLOR: Record<string,string> = {
  ACTIVE:'var(--success)', IDLE:'var(--warning)', CHARGING:'var(--accent-cyan)', ERROR:'var(--danger)'
}

export default function RobotCard({ robot, name }: Props) {
  const sc = STATUS_COLOR[robot.status] || 'var(--text-secondary)'
  return (
    <div className="card" style={{ padding:12 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
        <span style={{ fontFamily:'var(--font-mono)', fontSize:13, fontWeight:700, color:'var(--text-primary)' }}>
          🐕 {name}
        </span>
        <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color:sc,
          padding:'2px 6px', border:`1px solid ${sc}44`, borderRadius:2 }}>
          {robot.status}
        </span>
      </div>
      {[
        ['Task',    robot.task,                          'var(--accent-cyan)'],
        ['Battery', `${robot.battery.toFixed(0)}%`,      robot.battery > 50 ? 'var(--success)' : 'var(--warning)'],
        ['Speed',   `${robot.speed.toFixed(2)} m/s`,    'var(--text-primary)'],
        ['Pos',     `(${robot.pos.x.toFixed(1)}, ${robot.pos.y.toFixed(1)})`, 'var(--text-secondary)'],
      ].map(([k,v,c]) => (
        <div key={k as string} style={{ display:'flex', justifyContent:'space-between',
          padding:'4px 0', borderBottom:'1px solid var(--border)' }}>
          <span style={{ fontSize:10, color:'var(--text-secondary)' }}>{k}</span>
          <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color: c as string }}>{v}</span>
        </div>
      ))}
    </div>
  )
}
