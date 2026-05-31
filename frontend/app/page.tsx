'use client'
import { useState } from 'react'
import TopBar     from './components/layout/TopBar'
import Sidebar    from './components/layout/Sidebar'
import Overview   from './components/overview/Overview'
import CommandCenter from './components/command/CommandCenter'
import HealthPanel   from './components/twin/HealthPanel'
import VitalsChart   from './components/twin/VitalsChart'
import Robot3D       from './components/twin/Robot3D'
import CameraFeed    from './components/safety/CameraFeed'
import ZoneStatus    from './components/safety/ZoneStatus'
import IncidentLog   from './components/safety/IncidentLog'
import SafetyAlert   from './components/safety/SafetyAlert'
import FleetMap      from './components/fleet/FleetMap'
import RobotCard     from './components/fleet/RobotCard'
import TaskQueue     from './components/fleet/TaskQueue'
import CoordLog      from './components/fleet/CoordLog'
import VisionFeed    from './components/vision/VisionFeed'
import DetectionPanel from './components/vision/DetectionPanel'
import VLAStatus     from './components/vision/VLAStatus'
import Terminal      from './components/terminal/Terminal'
import { useMockData } from '../hooks/useMockData'

export type ViewId = 'overview'|'command'|'twin'|'safety'|'fleet'|'vision'|'terminal'

const GRID2 = { display:'grid', gridTemplateColumns:'2fr 1fr', gap:12, padding:12, height:'100%', overflow:'hidden' } as const
const COL   = { display:'flex', flexDirection:'column' as const, gap:12, overflow:'auto' }

export default function NexusDashboard() {
  const [view, setView] = useState<ViewId>('overview')
  const d = useMockData()

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100vh', overflow:'hidden' }}>
      <TopBar wsStatus={d.wsStatus} uptime={d.uptime} />
      <div style={{ display:'flex', flex:1, overflow:'hidden' }}>
        <Sidebar activeView={view} onViewChange={setView} data={d} />
        <main style={{ flex:1, overflow:'hidden', background:'var(--bg-primary)' }}>

          {view === 'overview'  && <Overview data={d} />}
          {view === 'command'   && <CommandCenter />}
          {view === 'terminal'  && <Terminal logs={d.logs} />}

          {view === 'twin' && (
            <div style={GRID2}>
              <Robot3D data={d.twin} />
              <div style={COL}>
                <HealthPanel data={d.twin} />
                <VitalsChart history={d.twinHistory} />
              </div>
            </div>
          )}

          {view === 'safety' && (
            <div style={GRID2}>
              <CameraFeed data={d.safety} />
              <div style={COL}>
                <ZoneStatus data={d.safety} />
                <IncidentLog data={d.safety} />
              </div>
            </div>
          )}

          {view === 'fleet' && (
            <div style={GRID2}>
              <FleetMap data={d.fleet} />
              <div style={COL}>
                <RobotCard robot={d.fleet.go2a} name="Go2-A" />
                <RobotCard robot={d.fleet.go2b} name="Go2-B" />
                <TaskQueue tasks={d.fleet.tasks} />
                <CoordLog  logs={d.fleet.coordLogs} />
              </div>
            </div>
          )}

          {view === 'vision' && (
            <div style={GRID2}>
              <VisionFeed data={d.vision} />
              <div style={COL}>
                <DetectionPanel data={d.vision} />
                <VLAStatus data={d.vision} />
              </div>
            </div>
          )}
        </main>
      </div>
      {d.safety.zone === 'DANGER' && <SafetyAlert />}
    </div>
  )
}
