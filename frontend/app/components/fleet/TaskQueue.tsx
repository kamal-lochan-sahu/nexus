"use client";

import React from "react";

interface Task {
  robot:    string;
  task:     string;
  priority: number;
  params:   Record<string, string>;
  status?:  "active" | "pending" | "done";
}

interface TaskQueueProps {
  tasks:    Task[];
  pending?: number;
}

const PRIORITY_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: "URGENT",  color: "bg-red-500/20 text-red-300 border-red-500/30" },
  2: { label: "HIGH",    color: "bg-amber-500/20 text-amber-300 border-amber-500/30" },
  3: { label: "NORMAL",  color: "bg-blue-500/20 text-blue-300 border-blue-500/30" },
  4: { label: "LOW",     color: "bg-gray-500/20 text-gray-300 border-gray-500/30" },
  5: { label: "ROUTINE", color: "bg-gray-500/20 text-gray-400 border-gray-500/20" },
};

const ROBOT_COLOR: Record<string, string> = {
  go2_a: "text-cyan-400",
  go2_b: "text-purple-400",
};

export default function TaskQueue({ tasks, pending = 0 }: TaskQueueProps) {
  const active  = tasks.filter(t => t.status === "active");
  const queued  = tasks.filter(t => t.status === "pending");

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5
                    backdrop-blur-sm p-4 flex flex-col gap-3">

      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="font-bold text-white text-sm">Task Queue</span>
        <div className="flex gap-2 text-xs">
          <span className="bg-green-500/20 text-green-300 border border-green-500/30
                           px-2 py-0.5 rounded-full">
            {active.length} active
          </span>
          <span className="bg-white/10 text-white/60 border border-white/10
                           px-2 py-0.5 rounded-full">
            {queued.length + pending} pending
          </span>
        </div>
      </div>

      {/* Active tasks */}
      {active.length > 0 && (
        <div>
          <div className="text-xs text-white/40 uppercase tracking-wider mb-2">
            Active
          </div>
          {active.map((t, i) => (
            <TaskRow key={i} task={t} />
          ))}
        </div>
      )}

      {/* Pending tasks */}
      {queued.length > 0 && (
        <div>
          <div className="text-xs text-white/40 uppercase tracking-wider mb-2">
            Pending
          </div>
          {queued.map((t, i) => (
            <TaskRow key={i} task={t} />
          ))}
        </div>
      )}

      {tasks.length === 0 && (
        <div className="text-center text-white/30 text-sm py-4">
          No tasks queued
        </div>
      )}
    </div>
  );
}

function TaskRow({ task }: { task: Task }) {
  const prio  = PRIORITY_LABELS[task.priority] ?? PRIORITY_LABELS[3];
  const rColor= ROBOT_COLOR[task.robot] ?? "text-white";
  const zone  = task.params?.zone ?? "";

  return (
    <div className="flex items-center gap-2 py-1.5 border-b border-white/5
                    last:border-0">
      <span className={`text-xs font-mono font-bold ${rColor} w-14 shrink-0`}>
        {task.robot.replace("_", "-").toUpperCase()}
      </span>
      <span className="text-sm text-white/80 flex-1 font-mono">
        {task.task}{zone ? ` / ${zone}` : ""}
      </span>
      <span className={`text-xs px-2 py-0.5 rounded-full border ${prio.color}`}>
        {prio.label}
      </span>
    </div>
  );
}
