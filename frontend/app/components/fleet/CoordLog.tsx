"use client";

import React, { useEffect, useRef } from "react";

interface CoordEvent {
  timestamp: number;
  robot?:    string;
  paused?:   string;
  active?:   string;
  event?:    string;
  detail?:   string;
  distance?: number;
}

interface CoordLogProps {
  events: CoordEvent[];
  maxVisible?: number;
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("en-IN", {
    hour:   "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatEvent(e: CoordEvent): { msg: string; color: string } {
  if (e.paused && e.distance) {
    return {
      msg:   `${e.paused.toUpperCase()} paused — proximity to ${e.active?.toUpperCase()} at ${e.distance.toFixed(2)}m`,
      color: "text-amber-300",
    };
  }
  if (e.event === "RESUMED") {
    return {
      msg:   `${e.robot?.toUpperCase()} resumed`,
      color: "text-green-300",
    };
  }
  if (e.event === "STOPPED") {
    return {
      msg:   `${e.robot?.toUpperCase()} stopped (${e.detail ?? ""})`,
      color: "text-red-300",
    };
  }
  return {
    msg:   `${e.robot?.toUpperCase() ?? "FLEET"} — ${e.event ?? ""} ${e.detail ?? ""}`,
    color: "text-white/60",
  };
}

export default function CoordLog({ events, maxVisible = 50 }: CoordLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  const visible = events.slice(-maxVisible);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5
                    backdrop-blur-sm p-4 flex flex-col gap-2">

      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-bold text-white text-sm">Coordination Log</span>
        <span className="text-xs text-white/40">{events.length} events</span>
      </div>

      {/* Log stream */}
      <div className="overflow-y-auto max-h-48 flex flex-col gap-1
                      scrollbar-thin scrollbar-thumb-white/10">
        {visible.length === 0 && (
          <div className="text-white/30 text-xs text-center py-4">
            No coordination events
          </div>
        )}
        {visible.map((e, i) => {
          const { msg, color } = formatEvent(e);
          return (
            <div key={i} className="flex gap-2 text-xs">
              <span className="text-white/30 shrink-0 font-mono w-20">
                {formatTime(e.timestamp)}
              </span>
              <span className={`${color}`}>{msg}</span>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
