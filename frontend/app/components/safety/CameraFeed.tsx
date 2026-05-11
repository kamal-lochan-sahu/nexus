"use client";
import { useEffect, useRef } from "react";

interface Landmark {
  x: number; y: number; z: number; v: number;
}

interface Props {
  zone: string;
  distance_m: number;
  landmarks?: Landmark[];
  width?: number;
  height?: number;
}

const ZONE_COLORS: Record<string, string> = {
  A: "#ef4444",
  B: "#f97316",
  C: "#22c55e",
  NONE: "#9ca3af",
};

// MediaPipe Pose connections (simplified major ones)
const CONNECTIONS = [
  [11,12],[11,13],[13,15],[12,14],[14,16],
  [11,23],[12,24],[23,24],[23,25],[25,27],
  [24,26],[26,28],[27,29],[28,30],
];

export default function CameraFeed({
  zone, distance_m, landmarks, width = 640, height = 480,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const color = ZONE_COLORS[zone] ?? "#9ca3af";

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Clear
    ctx.clearRect(0, 0, width, height);

    // Background
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, width, height);

    // No human placeholder
    if (!landmarks || landmarks.length < 33) {
      ctx.fillStyle = "#475569";
      ctx.font = "bold 22px monospace";
      ctx.textAlign = "center";
      ctx.fillText("No Human Detected", width / 2, height / 2);
      drawHUD(ctx, zone, distance_m, color, width);
      return;
    }

    // Skeleton connections
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
    for (const [a, b] of CONNECTIONS) {
      const la = landmarks[a], lb = landmarks[b];
      if (la.v < 0.3 || lb.v < 0.3) continue;
      ctx.beginPath();
      ctx.moveTo(la.x * width, la.y * height);
      ctx.lineTo(lb.x * width, lb.y * height);
      ctx.stroke();
    }

    // Landmark dots
    for (const lm of landmarks) {
      if (lm.v < 0.3) continue;
      ctx.beginPath();
      ctx.arc(lm.x * width, lm.y * height, 4, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    }

    drawHUD(ctx, zone, distance_m, color, width);
  }, [zone, distance_m, landmarks, width, height, color]);

  return (
    <div className="relative rounded-xl overflow-hidden border-2"
         style={{ borderColor: color }}>
      <canvas ref={canvasRef} width={width} height={height}
              style={{ display: "block", width: "100%", height: "auto" }} />
    </div>
  );
}

function drawHUD(
  ctx: CanvasRenderingContext2D,
  zone: string, dist: number, color: string, w: number
) {
  // Top bar
  ctx.fillStyle = "rgba(0,0,0,0.75)";
  ctx.fillRect(0, 0, w, 52);

  ctx.fillStyle = color;
  ctx.font = "bold 26px monospace";
  ctx.textAlign = "left";
  ctx.fillText(`Zone ${zone}`, 14, 36);

  ctx.fillStyle = "#e2e8f0";
  ctx.font = "22px monospace";
  ctx.textAlign = "right";
  ctx.fillText(`${dist.toFixed(2)} m`, w - 14, 36);
}
