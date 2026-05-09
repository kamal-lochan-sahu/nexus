// frontend/app/components/twin/HealthPanel.tsx
// 12 joints health bars + prediction alert card

"use client";

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

interface HealthPanelProps {
  joints: Record<string, JointHealth>;
  prediction: Prediction;
}

const STATUS_COLOR = {
  ok:       "bg-green-500",
  warning:  "bg-amber-500",
  critical: "bg-red-500",
};

const STATUS_TEXT = {
  ok:       "text-green-400",
  warning:  "text-amber-400",
  critical: "text-red-400",
};

export default function HealthPanel({ joints, prediction }: HealthPanelProps) {
  const jointList = Object.entries(joints);

  return (
    <div className="flex flex-col gap-3 h-full">

      {/* Prediction Alert */}
      {prediction?.joint && prediction.severity !== "ok" && (
        <div className={`rounded-lg p-3 border ${
          prediction.severity === "critical"
            ? "bg-red-950 border-red-700"
            : "bg-amber-950 border-amber-700"
        }`}>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg">{prediction.severity === "critical" ? "🚨" : "⚠️"}</span>
            <span className="text-white font-bold text-sm">
              {prediction.joint}: {Math.round((1 - prediction.confidence) * 100)}% health
            </span>
          </div>
          <p className="text-slate-300 text-xs mb-2">
            Failure predicted in ~{prediction.fail_in_hours}hrs
            &nbsp;·&nbsp; Confidence: {Math.round(prediction.confidence * 100)}%
          </p>
          <button className="w-full py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition">
            Schedule Maintenance
          </button>
        </div>
      )}

      {/* Joint health bars */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-1">
        {jointList.map(([name, data]) => (
          <div key={name}>
            <div className="flex justify-between items-center mb-0.5">
              <span className="text-slate-300 text-xs font-mono">{name}</span>
              <div className="flex items-center gap-2">
                <span className="text-slate-400 text-xs">{data.temp}°C</span>
                <span className={`text-xs font-bold ${STATUS_TEXT[data.status] ?? "text-slate-400"}`}>
                  {Math.round(data.health)}%
                </span>
              </div>
            </div>
            <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${STATUS_COLOR[data.status] ?? "bg-slate-500"}`}
                style={{ width: `${data.health}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-700">
        {(["ok","warning","critical"] as const).map(s => (
          <div key={s} className="text-center">
            <div className={`text-lg font-bold ${STATUS_TEXT[s]}`}>
              {jointList.filter(([,d]) => d.status === s).length}
            </div>
            <div className="text-slate-500 text-xs capitalize">{s}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
