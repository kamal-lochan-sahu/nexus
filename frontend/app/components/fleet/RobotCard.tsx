"use client";

import React from "react";

interface RobotCardProps {
  robotId:  string;       // "go2_a" | "go2_b"
  status:   string;       // "active" | "paused" | "stopped" | "idle"
  task:     string;
  position: { x: number; y: number };
  battery:  number;       // 0-100
  speed:    number;       // m/s
  onCommand?: () => void;
  onPause?:   () => void;
  onStop?:    () => void;
}

const STATUS_COLORS: Record<string, string> = {
  active:   "bg-green-500",
  paused:   "bg-amber-400",
  stopped:  "bg-red-500",
  idle:     "bg-gray-400",
  charging: "bg-blue-400",
};

const STATUS_RING: Record<string, string> = {
  active:  "ring-green-400",
  paused:  "ring-amber-300",
  stopped: "ring-red-400",
  idle:    "ring-gray-400",
};

export default function RobotCard({
  robotId, status, task, position, battery, speed,
  onCommand, onPause, onStop,
}: RobotCardProps) {
  const label      = robotId.replace("_", "-").toUpperCase();
  const dotColor   = STATUS_COLORS[status] ?? "bg-gray-400";
  const ringColor  = STATUS_RING[status]   ?? "ring-gray-300";
  const battColor  = battery > 50 ? "bg-green-500"
                   : battery > 20 ? "bg-amber-400" : "bg-red-500";

  return (
    <div className={`rounded-2xl border border-white/10 bg-white/5
                     backdrop-blur-sm p-4 ring-1 ${ringColor}
                     flex flex-col gap-3 min-w-[220px]`}>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${dotColor} animate-pulse`} />
          <span className="font-bold text-white text-sm">{label}</span>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium
          ${dotColor} text-white/90`}>
          {status.toUpperCase()}
        </span>
      </div>

      {/* Task */}
      <div className="text-xs text-white/60 uppercase tracking-wide">Task</div>
      <div className="text-sm font-mono text-cyan-300 truncate">{task || "—"}</div>

      {/* Position */}
      <div className="grid grid-cols-2 gap-2 text-xs text-white/70">
        <div>
          <span className="text-white/40">X </span>
          {position.x.toFixed(2)}m
        </div>
        <div>
          <span className="text-white/40">Y </span>
          {position.y.toFixed(2)}m
        </div>
        <div>
          <span className="text-white/40">⚡ </span>
          {speed.toFixed(2)} m/s
        </div>
        <div className="flex items-center gap-1">
          <span className="text-white/40">🔋</span>
          <div className="flex-1 bg-white/10 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full ${battColor}`}
              style={{ width: `${battery}%` }}
            />
          </div>
          <span>{battery}%</span>
        </div>
      </div>

      {/* Buttons */}
      <div className="flex gap-2 pt-1">
        <button
          onClick={onCommand}
          className="flex-1 text-xs bg-cyan-600 hover:bg-cyan-500
                     text-white rounded-lg py-1.5 font-medium transition"
        >
          COMMAND
        </button>
        <button
          onClick={onPause}
          className="flex-1 text-xs bg-amber-600 hover:bg-amber-500
                     text-white rounded-lg py-1.5 font-medium transition"
        >
          PAUSE
        </button>
        <button
          onClick={onStop}
          className="flex-1 text-xs bg-red-600 hover:bg-red-500
                     text-white rounded-lg py-1.5 font-medium transition"
        >
          STOP
        </button>
      </div>
    </div>
  );
}
