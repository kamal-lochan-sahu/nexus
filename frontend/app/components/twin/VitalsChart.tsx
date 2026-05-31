'use client'
import { LineChart, Line, ResponsiveContainer, Tooltip, YAxis, ReferenceLine } from 'recharts'

interface Props { history: number[] }

export default function VitalsChart({ history }: Props) {
  const chartData = history.map((v, i) => ({ i, v }))
  const latest = history[history.length - 1] ?? 0

  return (
    <div className="card" style={{ padding:14, flex:1 }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:8 }}>
        <p className="label">HEALTH HISTORY</p>
        <span style={{ fontFamily:'var(--font-mono)', fontSize:11, color:'var(--accent-cyan)' }}>
          {latest.toFixed(1)}%
        </span>
      </div>
      <ResponsiveContainer width="100%" height={100}>
        <LineChart data={chartData} margin={{ top:4, right:4, bottom:0, left:0 }}>
          <YAxis domain={[80,100]} hide/>
          <ReferenceLine y={90} stroke="var(--border)" strokeDasharray="3 3"/>
          <Tooltip
            contentStyle={{ background:'var(--bg-card)', border:'1px solid var(--border)',
              borderRadius:3, fontSize:10, fontFamily:'var(--font-mono)' }}
            formatter={(v: number) => [`${v.toFixed(1)}%`, 'Health']}
            labelFormatter={() => ''}
          />
          <Line type="monotone" dataKey="v" stroke="var(--accent-cyan)"
            strokeWidth={1.5} dot={false} animationDuration={200}/>
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
