// frontend/app/twin/page.tsx
// CognitiveTwin dashboard — Step 12
// WebSocket se live data, Three.js + HealthPanel + VitalsChart

"use client";
import { useEffect, useState, useRef } from "react";
import dynamic from "next/dynamic";
import HealthPanel from "../components/twin/HealthPanel";
import VitalsChart from "../components/twin/VitalsChart";

// Three.js SSR disable karo — server side render nahi hoga
const Robot3D = dynamic(() => import("../components/twin/Robot3D"), { ssr: false });

interface JointHealth {
  health: number;
  temp: number;
  status: "ok" | "warning" | "critical";
}

interface Prediction {
  joint: string;
  fail_in_hours: number;
  confidence: number;
  severity: string;
}

const DEFAULT_JOINTS = Object.fromEntries(
  ["FR_hip","FR_thigh","FR_calf","FL_hip","FL_thigh","FL_calf",
   "RR_hip","RR_thigh","RR_calf","RL_hip","RL_thigh","RL_calf"]
  .map(n => [n, { health: 100, temp: 40, status: "ok" as const }])
);

export default function TwinPage() {
  const [joints, setJoints]         = useState<Record<string, JointHealth>>(DEFAULT_JOINTS);
  const [prediction, setPrediction] = useState<Prediction>({} as Prediction);
  const [robot, setRobot]           = useState({ pos_x: 0, pos_y: 0, velocity: 0, gait: "stand" });
  const [wsStatus, setWsStatus]     = useState<"connecting"|"live"|"disconnected">("connecting");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket("ws://localhost:8000/ws");
      wsRef.current = ws;

      ws.onopen  = () => setWsStatus("live");
      ws.onclose = () => { setWsStatus("disconnected"); setTimeout(connect, 3000); };
      ws.onerror = () => ws.close();

      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.twin?.joints)     setJoints(data.twin.joints);
        if (data.twin?.prediction) setPrediction(data.twin.prediction);
        if (data.robot)            setRobot(data.robot);
      };
    };
    connect();
    return () => wsRef.current?.close();
  }, []);

  const statusColor = { live: "text-green-400", connecting: "text-amber-400", disconnected: "text-red-400" };
  const criticalCount = Object.values(joints).filter(j => j.status === "critical").length;

  return (
    <div className="min-h-screen bg-slate-950 text-white p-4">

      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-white">CognitiveTwin</h1>
          <p className="text-slate-400 text-sm">Go2 Digital Twin — Live Health Monitor</p>
        </div>
        <div className="flex items-center gap-4">
          {criticalCount > 0 && (
            <span className="bg-red-900 text-red-300 text-xs px-3 py-1 rounded-full font-semibold animate-pulse">
              🚨 {criticalCount} Critical
            </span>
          )}
          <div className="text-right">
            <div className={`text-xs font-semibold ${statusColor[wsStatus]}`}>
              ● {wsStatus.toUpperCase()}
            </div>
            <div className="text-slate-500 text-xs">
              {robot.gait} · {robot.velocity.toFixed(2)} m/s
            </div>
          </div>
        </div>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-12 gap-4" style={{ height: "calc(100vh - 120px)" }}>

        {/* 3D Robot viewer */}
        <div className="col-span-7 bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
          <div className="px-4 py-2 border-b border-slate-800 flex items-center justify-between">
            <span className="text-sm font-semibold text-slate-300">3D Model</span>
            <span className="text-xs text-slate-500">
              x:{robot.pos_x.toFixed(2)} y:{robot.pos_y.toFixed(2)}
            </span>
          </div>
          <div style={{ height: "calc(100% - 41px)" }}>
            <Robot3D joints={joints} />
          </div>
        </div>

        {/* Health panel */}
        <div className="col-span-5 bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
          <div className="px-4 py-2 border-b border-slate-800">
            <span className="text-sm font-semibold text-slate-300">Joint Health</span>
          </div>
          <div className="p-3 h-full">
            <HealthPanel joints={joints} prediction={prediction} />
          </div>
        </div>

        {/* Vitals chart — full width bottom */}
        <div className="col-span-12 bg-slate-900 rounded-xl border border-slate-800" style={{ height: 200 }}>
          <div className="px-4 py-2 border-b border-slate-800">
            <span className="text-sm font-semibold text-slate-300">Vitals — 30 min history</span>
          </div>
          <div style={{ height: 158 }}>
            <VitalsChart joints={joints} />
          </div>
        </div>

      </div>
    </div>
  );
}
