"use client";

interface Props {
  zone: string;
  distance_m: number;
  speed_override: number;
  speed_multiplier: number;
  human_detected: boolean;
}

const ZONES = [
  {
    id: "A",
    label: "Zone A",
    range: "< 1.5 m",
    action: "FULL STOP",
    activeClass: "bg-red-600 text-white shadow-[0_0_24px_rgba(239,68,68,0.6)]",
    inactiveClass: "bg-slate-800 text-slate-400 border border-slate-700",
    dot: "bg-red-500",
  },
  {
    id: "B",
    label: "Zone B",
    range: "1.5 – 3.0 m",
    action: "20% Speed",
    activeClass: "bg-orange-500 text-white shadow-[0_0_24px_rgba(249,115,22,0.5)]",
    inactiveClass: "bg-slate-800 text-slate-400 border border-slate-700",
    dot: "bg-orange-400",
  },
  {
    id: "C",
    label: "Zone C",
    range: "> 3.0 m",
    action: "Normal Op",
    activeClass: "bg-green-600 text-white shadow-[0_0_24px_rgba(34,197,94,0.4)]",
    inactiveClass: "bg-slate-800 text-slate-400 border border-slate-700",
    dot: "bg-green-500",
  },
];

export default function ZoneStatus({
  zone, distance_m, speed_override, speed_multiplier, human_detected
}: Props) {
  return (
    <div className="space-y-3">
      {ZONES.map((z) => {
        const active = zone === z.id;
        return (
          <div
            key={z.id}
            className={`rounded-xl p-4 flex items-center gap-4 transition-all duration-300
              ${active ? z.activeClass : z.inactiveClass}`}
          >
            <div className={`w-3 h-3 rounded-full ${active ? z.dot : "bg-slate-600"}`} />
            <div className="flex-1">
              <div className="font-bold text-lg">{z.label}</div>
              <div className="text-sm opacity-75">{z.range} — {z.action}</div>
            </div>
            {active && (
              <div className="text-right text-sm font-mono">
                <div>{distance_m.toFixed(2)} m</div>
                <div>{(speed_multiplier * 100).toFixed(0)}% spd</div>
              </div>
            )}
          </div>
        );
      })}

      {/* Speed readout */}
      <div className="rounded-xl bg-slate-800 border border-slate-700 p-4 mt-2">
        <div className="text-slate-400 text-sm mb-1">Robot Speed Override</div>
        <div className="text-3xl font-black font-mono text-white">
          {speed_override.toFixed(2)}
          <span className="text-base font-normal text-slate-400 ml-1">m/s</span>
        </div>
        <div className="mt-2 h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${speed_multiplier * 100}%`,
              background: zone === "A" ? "#ef4444"
                        : zone === "B" ? "#f97316"
                        : "#22c55e",
            }}
          />
        </div>
      </div>
    </div>
  );
}
