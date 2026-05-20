"use client";

import React, { useEffect, useState, useCallback } from "react";
import RobotCard  from "../components/fleet/RobotCard";
import TaskQueue  from "../components/fleet/TaskQueue";
import CoordLog   from "../components/fleet/CoordLog";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS  = API.replace("http", "ws") + "/ws";

interface FleetStatus {
  tasks_active:         number;
  tasks_pending:        number;
  coordination_events:  number;
  go2_a_task:           string;
  go2_b_task:           string;
  go2_a_status:         string;
  go2_b_status:         string;
  go2_a_position:       { x: number; y: number };
  go2_b_position:       { x: number; y: number };
}

const DEFAULT_FLEET: FleetStatus = {
  tasks_active: 0, tasks_pending: 0, coordination_events: 0,
  go2_a_task: "idle", go2_b_task: "idle",
  go2_a_status: "idle", go2_b_status: "idle",
  go2_a_position: { x: 0, y: 0 },
  go2_b_position: { x: 0, y: 0 },
};

export default function FleetPage() {
  const [fleet,    setFleet]    = useState<FleetStatus>(DEFAULT_FLEET);
  const [coordLog, setCoordLog] = useState<any[]>([]);
  const [tasks,    setTasks]    = useState<any[]>([]);
  const [goal,     setGoal]     = useState("");
  const [loading,  setLoading]  = useState(false);
  const [msg,      setMsg]      = useState("");

  // WebSocket — real-time fleet status
  useEffect(() => {
    const ws = new WebSocket(WS);
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.fleet) setFleet(data.fleet);
      } catch {}
    };
    return () => ws.close();
  }, []);

  // Poll coord log every 2s
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const res  = await fetch(API + "/flexcell/log");
        const data = await res.json();
        setCoordLog(data.conflict_events ?? []);
      } catch {}
    }, 2000);
    return () => clearInterval(id);
  }, []);

  const submitGoal = useCallback(async () => {
    if (!goal.trim()) return;
    setLoading(true);
    setMsg("");
    try {
      const res  = await fetch(API + "/flexcell/task", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ goal }),
      });
      const data = await res.json();
      setTasks(data.tasks ?? []);
      setMsg("Accepted — " + (data.tasks?.length ?? 0) + " tasks assigned");
      setGoal("");
    } catch (e: any) {
      setMsg("Error: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [goal]);

  const robotAction = async (robot: string, action: string) => {
    await fetch(`${API}/flexcell/robot/${robot}/${action}`, { method: "POST" });
  };

  const activeTasks = tasks
    .filter((t: any) =>
      (t.robot === "go2_a" && fleet.go2_a_task.includes(t.task?.toLowerCase())) ||
      (t.robot === "go2_b" && fleet.go2_b_task.includes(t.task?.toLowerCase()))
    )
    .map((t: any) => ({ ...t, status: "active" as const }));

  const allTasksForQueue = tasks.map((t: any) => ({
    ...t,
    status: "active" as const,
  }));

  return (
    <main className="min-h-screen bg-[#0a0f1e] text-white p-6">
      <div className="max-w-5xl mx-auto flex flex-col gap-6">

        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white">FlexCell Fleet</h1>
          <p className="text-white/40 text-sm">
            Multi-robot coordination — Industry 5.0
          </p>
        </div>

        {/* Stats bar */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Active Tasks",   value: fleet.tasks_active },
            { label: "Pending",        value: fleet.tasks_pending },
            { label: "Coord Events",   value: fleet.coordination_events },
          ].map(s => (
            <div key={s.label}
              className="rounded-xl bg-white/5 border border-white/10 p-4 text-center">
              <div className="text-2xl font-bold text-cyan-400">{s.value}</div>
              <div className="text-xs text-white/40 mt-1">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Robot cards */}
        <div className="flex gap-4 flex-wrap">
          <RobotCard
            robotId="go2_a"
            status={fleet.go2_a_status}
            task={fleet.go2_a_task}
            position={fleet.go2_a_position}
            battery={85}
            speed={0.3}
            onCommand={() => {}}
            onPause={() => robotAction("go2_a", "pause")}
            onStop={() => robotAction("go2_a", "stop")}
          />
          <RobotCard
            robotId="go2_b"
            status={fleet.go2_b_status}
            task={fleet.go2_b_task}
            position={fleet.go2_b_position}
            battery={92}
            speed={0.3}
            onCommand={() => {}}
            onPause={() => robotAction("go2_b", "pause")}
            onStop={() => robotAction("go2_b", "stop")}
          />
        </div>

        {/* Goal input */}
        <div className="rounded-2xl border border-white/10 bg-white/5 p-4 flex flex-col gap-3">
          <label className="text-sm font-medium text-white/70">
            High-Level Goal
          </label>
          <div className="flex gap-2">
            <input
              value={goal}
              onChange={e => setGoal(e.target.value)}
              onKeyDown={e => e.key === "Enter" && submitGoal()}
              placeholder="e.g. Patrol entire factory floor"
              className="flex-1 bg-white/10 border border-white/10 rounded-xl
                         px-4 py-2 text-sm text-white placeholder-white/30
                         outline-none focus:ring-1 focus:ring-cyan-500"
            />
            <button
              onClick={submitGoal}
              disabled={loading}
              className="px-5 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50
                         text-white text-sm font-medium rounded-xl transition"
            >
              {loading ? "..." : "DEPLOY"}
            </button>
          </div>
          {msg && (
            <p className="text-xs text-green-400">{msg}</p>
          )}
        </div>

        {/* Task queue + Coord log */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <TaskQueue tasks={allTasksForQueue} pending={fleet.tasks_pending} />
          <CoordLog  events={coordLog} />
        </div>

      </div>
    </main>
  );
}
