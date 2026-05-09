// frontend/app/components/twin/VitalsChart.tsx
// Recharts 24hr line chart — temp / vibration / current
// Updates every 5 minutes via WebSocket

"use client";
import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer
} from "recharts";

interface VitalsChartProps {
  joints: Record<string, { health: number; temp: number; status: string }>;
}

interface DataPoint {
  time: string;
  avgTemp: number;
  minHealth: number;
  maxHealth: number;
}

export default function VitalsChart({ joints }: VitalsChartProps) {
  const [history, setHistory] = useState<DataPoint[]>([]);

  useEffect(() => {
    if (Object.keys(joints).length === 0) return;

    const vals   = Object.values(joints);
    const avgTemp = vals.reduce((s, j) => s + j.temp, 0) / vals.length;
    const healths = vals.map(j => j.health);

    const point: DataPoint = {
      time:      new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
      avgTemp:   Math.round(avgTemp * 10) / 10,
      minHealth: Math.round(Math.min(...healths) * 10) / 10,
      maxHealth: Math.round(Math.max(...healths) * 10) / 10,
    };

    setHistory(prev => {
      const updated = [...prev, point];
      return updated.slice(-60);   // last 60 points = 30 minutes
    });
  }, [joints]);

  if (history.length < 2) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        Collecting data...
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={history} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="time" tick={{ fill: "#64748b", fontSize: 10 }} interval="preserveStartEnd" />
        <YAxis tick={{ fill: "#64748b", fontSize: 10 }} />
        <Tooltip
          contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
          labelStyle={{ color: "#94a3b8" }}
        />
        <Legend wrapperStyle={{ fontSize: 11, color: "#94a3b8" }} />
        <Line type="monotone" dataKey="avgTemp"   name="Avg Temp (°C)"   stroke="#f59e0b" dot={false} strokeWidth={2} />
        <Line type="monotone" dataKey="minHealth" name="Min Health (%)"  stroke="#ef4444" dot={false} strokeWidth={2} />
        <Line type="monotone" dataKey="maxHealth" name="Max Health (%)"  stroke="#22c55e" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}
