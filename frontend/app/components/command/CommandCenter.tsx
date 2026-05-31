'use client'
import { useState, useRef, useEffect } from 'react'

interface CmdResult {
  id: number; input: string; ts: number
  intent: string; module: string; confidence: number
  safetyL1: 'PASS'|'FAIL'; safetyL2: 'PASS'|'FAIL'; status: string
}

const INTENTS: Record<string,{intent:string;module:string;conf:number}> = {
  default: { intent:'navigate_to_waypoint', module:'NL2RC', conf:0.91 },
}

const EXAMPLES = [
  'navigate to zone 2',
  'inspect zone 3 for obstacles',
  'return to base station',
  'increase patrol speed',
  'scan the factory floor',
]

function mockParse(input: string) {
  const kw = input.toLowerCase()
  if (kw.includes('navigat') || kw.includes('zone') || kw.includes('go to'))
    return { intent:'navigate_to_waypoint', module:'NL2RC', conf:0.94 }
  if (kw.includes('inspect') || kw.includes('scan'))
    return { intent:'inspect_area', module:'VLA+NL2RC', conf:0.89 }
  if (kw.includes('return') || kw.includes('base'))
    return { intent:'return_to_base', module:'NL2RC', conf:0.97 }
  if (kw.includes('speed') || kw.includes('fast'))
    return { intent:'set_velocity', module:'NL2RC', conf:0.88 }
  if (kw.includes('stop') || kw.includes('halt'))
    return { intent:'emergency_stop', module:'SAFETY', conf:0.99 }
  return { intent:'navigate_to_waypoint', module:'NL2RC', conf:0.85 }
}

export default function CommandCenter() {
  const [input, setInput]       = useState('')
  const [processing, setProc]   = useState(false)
  const [current, setCurrent]   = useState<CmdResult|null>(null)
  const [history, setHistory]   = useState<CmdResult[]>([])
  const [step, setStep]         = useState(0)
  const idRef = useRef(1)

  const STEPS = ['Parsing intent...', 'Safety L1 (keyword filter)...', 'Safety L2 (parameter clamp)...', 'Dispatching to robot...']

  const submit = async () => {
    if (!input.trim() || processing) return
    setProc(true); setStep(0)
    const parsed = mockParse(input)
    // Simulate pipeline steps
    for (let i = 0; i < STEPS.length; i++) {
      setStep(i)
      await new Promise(r => setTimeout(r, 400 + Math.random()*300))
    }
    const result: CmdResult = {
      id: idRef.current++, input, ts: Date.now(),
      ...parsed, safetyL1:'PASS', safetyL2:'PASS', status:'DISPATCHED',
    }
    setCurrent(result)
    setHistory(h => [result, ...h].slice(0, 20))
    setInput(''); setProc(false)
  }

  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12, padding:12, height:'100%', overflow:'hidden' }}>

      {/* Left: Input + Processing */}
      <div style={{ display:'flex', flexDirection:'column', gap:12 }}>

        {/* Input panel */}
        <div className="card" style={{ padding:14 }}>
          <p className="label" style={{ marginBottom:10 }}>NATURAL LANGUAGE COMMAND</p>
          <div style={{ display:'flex', gap:8 }}>
            <input value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submit()}
              placeholder="Type a robot command…"
              style={{ flex:1, background:'var(--bg-secondary)', border:'1px solid var(--border)',
                borderRadius:3, padding:'8px 12px', color:'var(--text-primary)', fontSize:13,
                fontFamily:'var(--font-mono)', outline:'none' }}/>
            <button onClick={submit} disabled={processing || !input.trim()}
              style={{ padding:'8px 16px', background:'var(--accent-cyan)', color:'#000',
                border:'none', borderRadius:3, fontWeight:700, fontSize:12, cursor:'pointer',
                fontFamily:'var(--font-mono)', opacity: processing||!input.trim() ? .5 : 1 }}>
              {processing ? '...' : 'SEND'}
            </button>
          </div>
          {/* Quick examples */}
          <div style={{ display:'flex', flexWrap:'wrap', gap:4, marginTop:8 }}>
            {EXAMPLES.map(ex => (
              <button key={ex} onClick={() => setInput(ex)}
                style={{ padding:'3px 8px', background:'var(--bg-primary)', border:'1px solid var(--border)',
                  borderRadius:2, color:'var(--text-secondary)', fontSize:10, cursor:'pointer',
                  fontFamily:'var(--font-mono)' }}>
                {ex}
              </button>
            ))}
          </div>
        </div>

        {/* AI Processing panel */}
        <div className="card" style={{ padding:14, flex:1 }}>
          <p className="label" style={{ marginBottom:10 }}>AI PROCESSING PIPELINE</p>
          {processing && (
            <div style={{ marginBottom:12 }}>
              {STEPS.map((s, i) => (
                <div key={s} style={{ display:'flex', alignItems:'center', gap:8, padding:'5px 0',
                  opacity: i <= step ? 1 : 0.3, transition:'opacity .3s' }}>
                  <span style={{ width:14, height:14, display:'flex', alignItems:'center', justifyContent:'center' }}>
                    {i < step
                      ? <span style={{ color:'var(--success)', fontSize:12 }}>✓</span>
                      : i === step
                      ? <span style={{ display:'inline-block', width:10, height:10, border:'2px solid var(--accent-cyan)',
                          borderTopColor:'transparent', borderRadius:'50%', animation:'spin .6s linear infinite' }}/>
                      : <span style={{ color:'var(--border)', fontSize:12 }}>○</span>
                    }
                  </span>
                  <span style={{ fontFamily:'var(--font-mono)', fontSize:11,
                    color: i <= step ? 'var(--text-primary)' : 'var(--text-secondary)' }}>{s}</span>
                </div>
              ))}
            </div>
          )}
          {current && !processing && (
            <div style={{ display:'flex', flexDirection:'column', gap:6 }} className="fade-up">
              {[
                ['Intent',      current.intent,                 'var(--accent-cyan)'],
                ['Module',      current.module,                 'var(--text-primary)'],
                ['Safety L1',   current.safetyL1,               'var(--success)'],
                ['Safety L2',   current.safetyL2,               'var(--success)'],
                ['Confidence',  `${(current.confidence*100).toFixed(0)}%`, 'var(--accent-cyan)'],
                ['Status',      current.status,                 'var(--success)'],
              ].map(([k,v,c]) => (
                <div key={k as string} style={{ display:'flex', justifyContent:'space-between',
                  padding:'5px 8px', background:'var(--bg-secondary)', borderRadius:2 }}>
                  <span style={{ fontSize:11, color:'var(--text-secondary)', fontFamily:'var(--font-mono)' }}>{k}</span>
                  <span style={{ fontSize:11, color: c as string, fontFamily:'var(--font-mono)', fontWeight:600 }}>{v}</span>
                </div>
              ))}
            </div>
          )}
          {!current && !processing && (
            <p style={{ color:'var(--text-secondary)', fontSize:12, fontFamily:'var(--font-mono)' }}>
              Waiting for command…
            </p>
          )}
        </div>
      </div>

      {/* Right: History */}
      <div className="card" style={{ padding:14, overflow:'hidden', display:'flex', flexDirection:'column' }}>
        <p className="label" style={{ marginBottom:10 }}>COMMAND HISTORY ({history.length})</p>
        <div style={{ flex:1, overflow:'auto', display:'flex', flexDirection:'column', gap:6 }}>
          {history.length === 0 && (
            <p style={{ color:'var(--text-secondary)', fontSize:11, fontFamily:'var(--font-mono)' }}>No commands yet</p>
          )}
          {history.map(h => (
            <div key={h.id} style={{ padding:'8px 10px', background:'var(--bg-secondary)',
              borderRadius:3, border:'1px solid var(--border)' }}>
              <div style={{ display:'flex', justifyContent:'space-between', marginBottom:3 }}>
                <span style={{ fontSize:11, color:'var(--text-primary)', fontFamily:'var(--font-mono)', fontWeight:600 }}>
                  {h.input}
                </span>
                <span style={{ fontSize:10, color:'var(--text-secondary)', fontFamily:'var(--font-mono)' }}>
                  {new Date(h.ts).toLocaleTimeString()}
                </span>
              </div>
              <div style={{ display:'flex', gap:8 }}>
                <span style={{ fontSize:10, color:'var(--accent-cyan)', fontFamily:'var(--font-mono)' }}>{h.intent}</span>
                <span style={{ fontSize:10, color:'var(--success)', fontFamily:'var(--font-mono)' }}>{h.status}</span>
                <span style={{ fontSize:10, color:'var(--text-secondary)', fontFamily:'var(--font-mono)' }}>
                  conf:{(h.confidence*100).toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
