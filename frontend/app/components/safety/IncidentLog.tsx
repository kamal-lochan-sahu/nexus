"use client";
import { useEffect, useState } from "react";

interface Incident {
  id: number;
  ts: string;
  zone: string;
  distance_m: number;
  intent: string;
  resolved_at?: string;
}

interface Props {
  incidentsToday: number;
  slowdownsToday?: number;
}

export default function IncidentLog({ incidentsToday, slowdownsToday = 0 }: Props) {
  const [log, setLog] = useState<Incident[]>([]);

  // In production this would fetch from /api/safety/incidents
  // For now — simulated local log
  useEffect(() => {
    if (incidentsToday > log.length) {
      setLog((prev) => [
        {
          id: prev.length + 1,
          ts: new Date().toISOString(),
          zone: "A",
          distance_m: Math.random() * 0.5 + 0.8,
          intent: "approaching",
        },
        ...prev,
      ]);
    }
  }, [incidentsToday]);

  const zoneColor: Record<string, string> = {
    A: "text-red-400",
    B: "text-orange-400",
    C: "text-green-400",
  };

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-700 p-4">
      {/* Stats row */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[
          { label: "Incidents Today", value: incidentsToday, color: "text-red-400" },
          { label: "Slowdowns", value: slowdownsToday, color: "text-orange-400" },
          { label: "Avg Response", value: "<100ms", color: "text-green-400" },
        ].map((s) => (
          <div key={s.label}
               className="bg-slate-800 rounded-lg p-3 text-center border border-slate-700">
            <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
            <div className="text-slate-400 text-xs mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-y-auto max-h-48 text-sm font-mono">
        {log.length === 0 ? (
          <div className="text-slate-500 text-center py-6">
            No incidents — all clear ✓
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="text-slate-500 text-xs border-b border-slate-700">
                <th className="text-left pb-2">#</th>
                <th className="text-left pb-2">Time</th>
                <th className="text-left pb-2">Zone</th>
                <th className="text-left pb-2">Dist</th>
                <th className="text-left pb-2">Intent</th>
              </tr>
            </thead>
            <tbody>
              {log.map((inc) => (
                <tr key={inc.id}
                    className="border-b border-slate-800 hover:bg-slate-800/50">
                  <td className="py-1.5 text-slate-400">{inc.id}</td>
                  <td className="py-1.5 text-slate-300">
                    {new Date(inc.ts).toLocaleTimeString()}
                  </td>
                  <td className={`py-1.5 font-bold ${zoneColor[inc.zone]}`}>
                    {inc.zone}
                  </td>
                  <td className="py-1.5 text-slate-300">
                    {inc.distance_m.toFixed(2)}m
                  </td>
                  <td className="py-1.5 text-slate-300">{inc.intent}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
