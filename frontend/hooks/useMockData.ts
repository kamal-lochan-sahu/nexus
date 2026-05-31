'use client'
import { useState, useEffect, useRef } from 'react'

function wave(t:number, period:number, amp:number, center:number) {
  return center + Math.sin(t/period) * amp
}

export interface TwinData {
  health: number; battery: number; temp: number
  anomaly: number; joints: number[]; uptimeSec: number
}
export interface SafetyData {
  zone: 'CLEAR'|'WARNING'|'DANGER'; humanCount: number; incidents: number
  zones: {id:string; status:string; dist:number}[]
}
export interface RobotData {
  status: 'ACTIVE'|'IDLE'|'CHARGING'|'ERROR'
  task: string; battery: number; speed: number
  pos: {x:number; y:number; theta:number}
}
export interface FleetData {
  go2a: RobotData; go2b: RobotData
  tasks: {id:string; robot:string; type:string; status:string; progress:number}[]
  coordLogs: {ts:number; msg:string}[]
}
export interface VisionData {
  detections: {id:number; label:string; conf:number; bbox:[number,number,number,number]}[]
  vlaLatency: number; vlaStatus: string; fps: number
}
export interface LogEntry { id:number; level:string; module:string; msg:string; ts:number }

export interface MockData {
  twin: TwinData; twinHistory: number[]
  safety: SafetyData; fleet: FleetData
  vision: VisionData; logs: LogEntry[]
  kpis: {units:number; incidents:number; health:number; sr:number}
  wsStatus: 'MOCK'; uptime: number
}

const SEED_LOGS: LogEntry[] = [
  {id:1, level:'SUCCESS', module:'SYSTEM',  msg:'NEXUS platform initialized — all 6 modules OK', ts:Date.now()-90000},
  {id:2, level:'SUCCESS', module:'NL2RC',   msg:'Groq LLM connected — Llama-3.1-8b-instant', ts:Date.now()-80000},
  {id:3, level:'SUCCESS', module:'TWIN',    msg:'CognitiveTwin LSTM loaded — MAE=0.021', ts:Date.now()-70000},
  {id:4, level:'INFO',    module:'SAFETY',  msg:'ISO/TS 15066 zones active — 4 zones monitored', ts:Date.now()-60000},
  {id:5, level:'SUCCESS', module:'RL',      msg:'PPO agent online — navigation SR=85%', ts:Date.now()-50000},
  {id:6, level:'INFO',    module:'FLEET',   msg:'Go2-A: PATROL task assigned (zone Z1→Z4)', ts:Date.now()-40000},
  {id:7, level:'INFO',    module:'FLEET',   msg:'Go2-B: STANDBY — battery 42%, recharge soon', ts:Date.now()-30000},
  {id:8, level:'SUCCESS', module:'VLA',     msg:'EmbodiedGPT pipeline ready — avg latency 2.3s', ts:Date.now()-20000},
  {id:9, level:'INFO',    module:'WS',      msg:'Mock data stream active — 2Hz broadcast', ts:Date.now()-10000},
  {id:10,level:'SUCCESS', module:'SYSTEM',  msg:'Dashboard online — recruiter view ready', ts:Date.now()-2000},
]

const LOG_POOL = [
  {level:'INFO',    module:'NL2RC',   msgs:['Command received: navigate_to_zone_2','Safety L1 passed','Confidence: 0.94','Dispatched to Go2-A']},
  {level:'INFO',    module:'TWIN',    msgs:['Joint telemetry updated','Health: 94.2%','Anomaly score: 0.03 — NOMINAL','LSTM inference: 11ms']},
  {level:'INFO',    module:'SAFETY',  msgs:['Zone scan: CLEAR','Human detection: 0','E-stop: ARMED','ISO 15066: COMPLIANT']},
  {level:'SUCCESS', module:'RL',      msgs:['Waypoint reached','Path recalculated','Obstacle avoided — replanning']},
  {level:'WARNING', module:'FLEET',   msgs:['Go2-B battery: 42% — recharge in 18min','Separation 1.4m — reducing speed']},
  {level:'INFO',    module:'VLA',     msgs:['Object: pallet_box conf=0.94','Grasp pose computed','VLA pipeline: 2.3s','CLIP embedding: 45ms']},
  {level:'INFO',    module:'FLEET',   msgs:['Conflict resolved — 1.6m separation','Task T002 queued','Fleet scheduler: asyncio loop OK']},
]

export function useMockData(): MockData {
  const t0    = useRef(Date.now())
  const logId = useRef(11)

  const [data, setData] = useState<MockData>({
    twin: { health:94.2, battery:78, temp:42.3, anomaly:0.03, joints:Array(12).fill(0), uptimeSec:0 },
    twinHistory: Array(30).fill(94.2),
    safety: {
      zone:'CLEAR', humanCount:0, incidents:0,
      zones:[{id:'Z1',status:'CLEAR',dist:2.4},{id:'Z2',status:'CLEAR',dist:3.1},{id:'Z3',status:'CLEAR',dist:5.7},{id:'Z4',status:'CLEAR',dist:4.2}],
    },
    fleet: {
      go2a: { status:'ACTIVE',  task:'PATROL',  battery:78, speed:0.8, pos:{x:2.4,y:1.8,theta:45} },
      go2b: { status:'IDLE',    task:'STANDBY', battery:42, speed:0,   pos:{x:0.2,y:0.3,theta:0} },
      tasks:[
        {id:'T001',robot:'Go2-A',type:'PATROL',   status:'ACTIVE', progress:65},
        {id:'T002',robot:'Go2-B',type:'INSPECT',  status:'QUEUED', progress:0},
        {id:'T003',robot:'Go2-A',type:'NAVIGATE', status:'QUEUED', progress:0},
      ],
      coordLogs:[
        {ts:Date.now()-15000, msg:'Separation: 3.2m — OK'},
        {ts:Date.now()-10000, msg:'Conflict check passed'},
        {ts:Date.now()-5000,  msg:'Fleet sync: 2 robots, 3 tasks'},
      ],
    },
    vision: {
      detections:[
        {id:1,label:'pallet_box',   conf:0.94, bbox:[120,80,200,140]},
        {id:2,label:'safety_cone',  conf:0.87, bbox:[310,190,60,100]},
      ],
      vlaLatency:2.3, vlaStatus:'READY', fps:30,
    },
    logs: [...SEED_LOGS],
    kpis: { units:847, incidents:0, health:94.2, sr:85 },
    wsStatus: 'MOCK', uptime:0,
  })

  useEffect(() => {
    const iv = setInterval(() => {
      const now  = Date.now()
      const elap = (now - t0.current) / 1000

      setData(prev => {
        // Occasionally emit a log
        let logs = prev.logs
        if (Math.random() < 0.15) {
          const src = LOG_POOL[Math.floor(Math.random() * LOG_POOL.length)]
          const msg = src.msgs[Math.floor(Math.random() * src.msgs.length)]
          logs = [...prev.logs.slice(-49), {id:logId.current++, level:src.level, module:src.module, msg, ts:now}]
        }

        const health = Math.min(100, Math.max(85, wave(now, 8000, 2.5, 94.2)))
        return {
          ...prev,
          uptime: Math.floor(elap),
          twin: {
            health,
            battery:  Math.max(10, prev.twin.battery - 0.0015),
            temp:     wave(now, 6000, 1.8, 42.3),
            anomaly:  Math.max(0, Math.min(0.15, wave(now, 12000, 0.025, 0.03))),
            joints:   prev.twin.joints.map((_,i) => wave(now, 2500+i*400, 12, 0)),
            uptimeSec: Math.floor(elap),
          },
          twinHistory: [...prev.twinHistory.slice(1), parseFloat(health.toFixed(1))],
          fleet: {
            ...prev.fleet,
            go2a: {
              ...prev.fleet.go2a,
              speed: Math.max(0.2, wave(now, 5000, 0.3, 0.8)),
              pos: {
                x: wave(now, 10000, 2.2, 2.4),
                y: wave(now, 8000,  1.4, 1.8),
                theta: (elap * 4) % 360,
              },
            },
          },
          vision: {
            ...prev.vision,
            vlaLatency: wave(now, 4000, 0.4, 2.3),
            fps: Math.round(wave(now, 3000, 2, 30)),
          },
          kpis: {
            ...prev.kpis,
            health: parseFloat(health.toFixed(1)),
            units:  prev.kpis.units + (Math.random() < 0.008 ? 1 : 0),
          },
          logs,
        }
      })
    }, 500)
    return () => clearInterval(iv)
  }, [])

  return data
}
