"use client";

/**
 * NEXUS Phase 4 — Step 9
 * FleetMap — 2D top-down factory map
 *
 * Features:
 *   - SVG factory floor (6x6m arena)
 *   - Live robot position dot (WebSocket /odom)
 *   - RL path trace (where robot went)
 *   - Goal marker
 *   - Zone labels (A/B/C/D)
 *   - Obstacle positions
 *   - Updates at 2Hz via WebSocket
 */

import { useEffect, useRef, useState, useCallback } from "react";

// ── Types ──────────────────────────────────────────────────────────
interface RobotState {
  x: number;
  y: number;
  yaw: number;
  vx: number;
  wz: number;
}

interface GoalState {
  x: number;
  y: number;
  zone: string;
  reached: boolean;
}

interface Obstacle {
  x: number;
  y: number;
  r: number;
}

interface FleetMapProps {
  wsUrl?: string;
  width?: number;
  height?: number;
}

// ── Constants ──────────────────────────────────────────────────────
const ARENA_M   = 6.0;    // meters
const MAX_TRACE = 200;    // max path points stored

const ZONES = {
  A: { x: -2.5, y:  2.5, label: "A" },
  B: { x:  2.5, y:  2.5, label: "B" },
  C: { x: -2.5, y: -2.5, label: "C" },
  D: { x:  2.5, y: -2.5, label: "D" },
};

// ── Coordinate transform: world (m) → SVG (px) ────────────────────
function toSvg(worldX: number, worldY: number, svgSize: number) {
  const scale = svgSize / ARENA_M;
  const px = (worldX + ARENA_M / 2) * scale;
  const py = (ARENA_M / 2 - worldY) * scale;  // flip Y
  return { px, py };
}

// ── FleetMap Component ─────────────────────────────────────────────
export default function FleetMap({
  wsUrl   = "ws://localhost:8000/ws/fleet",
  width   = 480,
  height  = 480,
}: FleetMapProps) {
  const svgSize = Math.min(width, height);

  const [robot, setRobot] = useState<RobotState>({ x: 0, y: 0, yaw: 0, vx: 0, wz: 0 });
  const [goal,  setGoal]  = useState<GoalState | null>(null);
  const [obstacles, setObstacles] = useState<Obstacle[]>([]);
  const [pathTrace, setPathTrace] = useState<{ x: number; y: number }[]>([]);
  const [connected, setConnected] = useState(false);
  const [rlActive,  setRlActive]  = useState(false);

  const wsRef = useRef<WebSocket | null>(null);

  // ── WebSocket connection ─────────────────────────────────────────
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Robot state update
        if (data.type === "robot_state") {
          setRobot(prev => {
            const newState = {
              x:   data.x   ?? prev.x,
              y:   data.y   ?? prev.y,
              yaw: data.yaw ?? prev.yaw,
              vx:  data.vx  ?? prev.vx,
              wz:  data.wz  ?? prev.wz,
            };
            // Append to path trace
            setPathTrace(pt => {
              const next = [...pt, { x: newState.x, y: newState.y }];
              return next.length > MAX_TRACE ? next.slice(-MAX_TRACE) : next;
            });
            return newState;
          });
        }

        // Goal update
        if (data.type === "goal") {
          setGoal({
            x:       data.x,
            y:       data.y,
            zone:    data.zone ?? "",
            reached: data.reached ?? false,
          });
        }

        // Obstacles
        if (data.type === "obstacles") {
          setObstacles(data.obstacles ?? []);
        }

        // RL status
        if (data.type === "rl_status") {
          setRlActive(data.active ?? false);
        }

      } catch { /* ignore malformed */ }
    };

    ws.onclose = () => {
      setConnected(false);
      // Reconnect after 2s
      setTimeout(connect, 2000);
    };

    ws.onerror = () => ws.close();

    wsRef.current = ws;
  }, [wsUrl]);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  // ── Clear path trace ─────────────────────────────────────────────
  const clearTrace = () => setPathTrace([]);

  // ── Render ───────────────────────────────────────────────────────
  const robotSvg = toSvg(robot.x, robot.y, svgSize);
  const scale    = svgSize / ARENA_M;

  // Path trace as SVG polyline points
  const tracePoints = pathTrace
    .map(p => {
      const s = toSvg(p.x, p.y, svgSize);
      return `${s.px},${s.py}`;
    })
    .join(" ");

  return (
    <div className="flex flex-col gap-3">

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">FleetMap</h2>
        <div className="flex items-center gap-2">
          {rlActive && (
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-500/20 text-blue-400 border border-blue-500/30">
              RL ACTIVE
            </span>
          )}
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
            connected
              ? "bg-green-500/20 text-green-400 border border-green-500/30"
              : "bg-red-500/20 text-red-400 border border-red-500/30"
          }`}>
            {connected ? "LIVE" : "OFFLINE"}
          </span>
        </div>
      </div>

      {/* ── SVG Map ── */}
      <div className="rounded-xl overflow-hidden border border-white/10 bg-[#0a0a0f]">
        <svg
          width={svgSize}
          height={svgSize}
          viewBox={`0 0 ${svgSize} ${svgSize}`}
          className="block"
        >
          {/* Arena background */}
          <rect x={0} y={0} width={svgSize} height={svgSize} fill="#0d1117" />

          {/* Grid lines (1m spacing) */}
          {[-2, -1, 0, 1, 2].map(i => {
            const { px } = toSvg(i, 0, svgSize);
            const { py } = toSvg(0, i, svgSize);
            return (
              <g key={i}>
                <line x1={px} y1={0} x2={px} y2={svgSize}
                      stroke="#1e2433" strokeWidth={1} />
                <line x1={0} y1={py} x2={svgSize} y2={py}
                      stroke="#1e2433" strokeWidth={1} />
              </g>
            );
          })}

          {/* Arena border */}
          <rect x={1} y={1} width={svgSize-2} height={svgSize-2}
                fill="none" stroke="#334155" strokeWidth={2} />

          {/* Zone labels */}
          {Object.entries(ZONES).map(([key, zone]) => {
            const s = toSvg(zone.x, zone.y, svgSize);
            return (
              <g key={key}>
                <circle cx={s.px} cy={s.py} r={24}
                        fill="#1e2433" stroke="#334155" strokeWidth={1} />
                <text x={s.px} y={s.py + 5} textAnchor="middle"
                      fill="#64748b" fontSize={14} fontWeight="600">
                  {key}
                </text>
              </g>
            );
          })}

          {/* Obstacles */}
          {obstacles.map((obs, i) => {
            const s = toSvg(obs.x, obs.y, svgSize);
            const r = obs.r * scale;
            return (
              <circle key={i} cx={s.px} cy={s.py} r={r}
                      fill="#ef444420" stroke="#ef4444" strokeWidth={1.5} />
            );
          })}

          {/* RL Path trace */}
          {pathTrace.length > 1 && (
            <polyline
              points={tracePoints}
              fill="none"
              stroke="#3b82f6"
              strokeWidth={2}
              strokeOpacity={0.7}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Goal marker */}
          {goal && (() => {
            const s = toSvg(goal.x, goal.y, svgSize);
            return (
              <g>
                {/* Pulsing ring */}
                <circle cx={s.px} cy={s.py} r={14}
                        fill="none"
                        stroke={goal.reached ? "#22c55e" : "#f59e0b"}
                        strokeWidth={2}
                        strokeDasharray="4 2"
                        opacity={0.8} />
                {/* Center dot */}
                <circle cx={s.px} cy={s.py} r={5}
                        fill={goal.reached ? "#22c55e" : "#f59e0b"} />
                {/* Zone label */}
                {goal.zone && (
                  <text x={s.px} y={s.py - 18} textAnchor="middle"
                        fill={goal.reached ? "#22c55e" : "#f59e0b"}
                        fontSize={11} fontWeight="600">
                    GOAL {goal.zone}
                  </text>
                )}
              </g>
            );
          })()}

          {/* Robot */}
          <g transform={`translate(${robotSvg.px}, ${robotSvg.py}) rotate(${-robot.yaw * 180 / Math.PI})`}>
            {/* Body */}
            <circle cx={0} cy={0} r={10}
                    fill={rlActive ? "#3b82f6" : "#94a3b8"}
                    stroke={rlActive ? "#60a5fa" : "#cbd5e1"}
                    strokeWidth={2} />
            {/* Direction arrow */}
            <line x1={0} y1={0} x2={13} y2={0}
                  stroke={rlActive ? "#93c5fd" : "#e2e8f0"}
                  strokeWidth={2.5}
                  strokeLinecap="round" />
          </g>

          {/* Origin cross */}
          <line x1={svgSize/2-6} y1={svgSize/2} x2={svgSize/2+6} y2={svgSize/2}
                stroke="#334155" strokeWidth={1} />
          <line x1={svgSize/2} y1={svgSize/2-6} x2={svgSize/2} y2={svgSize/2+6}
                stroke="#334155" strokeWidth={1} />
        </svg>
      </div>

      {/* ── Robot telemetry ── */}
      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
        <div className="rounded-lg bg-white/5 border border-white/10 p-2">
          <div className="text-slate-400 mb-1">Position</div>
          <div className="text-white">
            x: {robot.x.toFixed(2)}m &nbsp; y: {robot.y.toFixed(2)}m
          </div>
        </div>
        <div className="rounded-lg bg-white/5 border border-white/10 p-2">
          <div className="text-slate-400 mb-1">Velocity</div>
          <div className="text-white">
            vx: {robot.vx.toFixed(2)} &nbsp; ω: {robot.wz.toFixed(2)}
          </div>
        </div>
        {goal && (
          <div className="col-span-2 rounded-lg bg-white/5 border border-white/10 p-2">
            <div className="text-slate-400 mb-1">Goal</div>
            <div className={goal.reached ? "text-green-400" : "text-amber-400"}>
              Zone {goal.zone} ({goal.x.toFixed(1)}, {goal.y.toFixed(1)})
              {goal.reached ? " — ✅ REACHED" : " — navigating..."}
            </div>
          </div>
        )}
      </div>

      {/* ── Controls ── */}
      <button
        onClick={clearTrace}
        className="text-xs text-slate-400 hover:text-white transition-colors text-left"
      >
        Clear path trace
      </button>
    </div>
  );
}
