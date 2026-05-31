'use client'
import { MockData } from '../../../hooks/useMockData'

type ViewId = 'overview'|'command'|'twin'|'safety'|'fleet'|'vision'|'terminal'

interface Props { activeView: ViewId; onViewChange: (v: ViewId) => void; data: MockData }

const VIEWS: {id: ViewId; label: string; icon: string}[] = [
  {id:'overview', label:'Overview',     icon:'M3 3h8v8H3zm10 0h8v8h-8zM3 13h8v8H3zm10 0h8v8h-8z'},
  {id:'command',  label:'Command',      icon:'M5 12l2-2 3 3 7-7 2 2-9 9z'},
  {id:'twin',     label:'Digital Twin', icon:'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5'},
  {id:'safety',   label:'Safety',       icon:'M12 2L4 6v6c0 5.5 3.8 10.7 8 12 4.2-1.3 8-6.5 8-12V6l-8-4z'},
  {id:'fleet',    label:'Fleet',        icon:'M12 2a5 5 0 100 10A5 5 0 0012 2zm-7 13a7 7 0 0114 0v1H5v-1z'},
  {id:'vision',   label:'Vision',       icon:'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zm11-3a3 3 0 100 6 3 3 0 000-6z'},
  {id:'terminal', label:'Terminal',     icon:'M4 6l4 4-4 4m8 0h4'},
]

export default function Sidebar({ activeView, onViewChange, data }: Props) {
  const goA = data.fleet.go2a
  const goB = data.fleet.go2b

  const robotColor = (s: string) =>
    s === 'ACTIVE' ? 'var(--success)' : s === 'IDLE' ? 'var(--warning)' : 'var(--danger)'

  return (
    <aside style={{ width:200, background:'var(--bg-secondary)', borderRight:'1px solid var(--border)',
      display:'flex', flexDirection:'column', flexShrink:0, overflow:'hidden' }}>

      {/* Nav */}
      <nav style={{ padding:'8px 0', flex:1 }}>
        {VIEWS.map(v => {
          const active = v.id === activeView
          return (
            <button key={v.id} onClick={() => onViewChange(v.id)}
              style={{
                display:'flex', alignItems:'center', gap:10,
                width:'100%', padding:'10px 16px', border:'none', cursor:'pointer',
                background: active ? 'rgba(0,212,255,.08)' : 'transparent',
                borderLeft: active ? '2px solid var(--accent-cyan)' : '2px solid transparent',
                color: active ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                fontFamily:'var(--font-sans)', fontSize:12, fontWeight: active ? 600 : 400,
                transition:'all .2s', textAlign:'left',
              }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={v.icon}/>
              </svg>
              {v.label}
            </button>
          )
        })}
      </nav>

      {/* Fleet Status */}
      <div style={{ padding:'12px 14px', borderTop:'1px solid var(--border)' }}>
        <p className="label" style={{ marginBottom:8 }}>FLEET STATUS</p>
        {[['Go2-A 🐕', goA.status], ['Go2-B 🐕', goB.status]].map(([nm, st, bat]) => (
          <div key={nm as string} style={{ display:'flex', alignItems:'center', justifyContent:'space-between',
            marginBottom:6, fontSize:11, fontFamily:'var(--font-mono)' }}>
            <span style={{ color:'var(--text-secondary)' }}>{nm}</span>
            <div style={{ display:'flex', alignItems:'center', gap:4 }}>
              <span style={{ color: robotColor(st as string), fontSize:10 }}>{st}</span>
              <span className="dot" style={{ width:5, height:5, background: robotColor(st as string), borderRadius:'50%' }}/>
            </div>
          </div>
        ))}
        <div style={{ fontSize:10, color:'var(--text-secondary)', fontFamily:'var(--font-mono)', marginTop:6 }}>
          KPIs: {data.kpis.units} units · SR {data.kpis.sr}%
        </div>
      </div>
    </aside>
  )
}
