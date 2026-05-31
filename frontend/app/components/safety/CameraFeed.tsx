'use client'
import { SafetyData } from '../../../hooks/useMockData'

interface Props { data: SafetyData }

export default function CameraFeed({ data }: Props) {
  const statusColor = data.zone === 'CLEAR' ? 'var(--success)' : data.zone === 'WARNING' ? 'var(--warning)' : 'var(--danger)'

  return (
    <div className="card" style={{ position:'relative', overflow:'hidden', display:'flex', flexDirection:'column' }}>
      <div style={{ display:'flex', justifyContent:'space-between', padding:'10px 12px',
        borderBottom:'1px solid var(--border)', flexShrink:0 }}>
        <p className="label">SAFETY CAMERA — ISO/TS 15066</p>
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <span style={{ fontFamily:'var(--font-mono)', fontSize:10, color: statusColor }}>{data.zone}</span>
          <span className={`dot ${data.zone==='CLEAR'?'dot-on':data.zone==='WARNING'?'dot-warn':'dot-err'}`}/>
        </div>
      </div>

      {/* Mock camera view */}
      <div className="factory-grid" style={{ flex:1, position:'relative', background:'var(--bg-primary)', minHeight:200 }}>
        {/* Scan line animation */}
        <div style={{ position:'absolute', left:0, right:0, height:2,
          background:'linear-gradient(90deg,transparent,var(--accent-cyan),transparent)',
          animation:'scan 3s linear infinite', opacity:.6, zIndex:2 }}/>

        {/* Detection boxes (simulated) */}
        <div style={{ position:'absolute', left:'25%', top:'30%', width:'22%', height:'28%',
          border:'2px solid var(--accent-cyan)', borderRadius:2 }}>
          <span style={{ position:'absolute', top:-16, left:0, fontSize:9, background:'var(--accent-cyan)',
            color:'#000', padding:'1px 4px', fontFamily:'monospace', fontWeight:700 }}>
            pallet_box 0.94
          </span>
        </div>
        <div style={{ position:'absolute', left:'62%', top:'45%', width:'10%', height:'20%',
          border:'2px solid var(--warning)', borderRadius:2 }}>
          <span style={{ position:'absolute', top:-16, left:0, fontSize:9, background:'var(--warning)',
            color:'#000', padding:'1px 4px', fontFamily:'monospace', fontWeight:700 }}>
            cone 0.87
          </span>
        </div>

        {/* Crosshair center */}
        <div style={{ position:'absolute', left:'50%', top:'50%', transform:'translate(-50%,-50%)',
          width:20, height:20, opacity:.4 }}>
          <div style={{ position:'absolute', left:'50%', top:0, bottom:0, width:1, background:'var(--text-secondary)' }}/>
          <div style={{ position:'absolute', top:'50%', left:0, right:0, height:1, background:'var(--text-secondary)' }}/>
        </div>

        {/* Overlay info */}
        <div style={{ position:'absolute', bottom:8, left:8, fontFamily:'var(--font-mono)', fontSize:10, color:'var(--success)' }}>
          REC ● {new Date().toLocaleTimeString('en-GB')} · 30fps
        </div>
        <div style={{ position:'absolute', top:8, right:8, fontFamily:'var(--font-mono)', fontSize:10, color:'var(--text-secondary)' }}>
          CAM-01 · WIDE · f/2.4
        </div>
      </div>
    </div>
  )
}
