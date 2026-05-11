"use client";
import { useEffect, useRef, useState } from "react";

interface Props {
  zone: string;
  onDismiss?: () => void;
}

export default function SafetyAlert({ zone, onDismiss }: Props) {
  const [visible, setVisible] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const oscillatorRef = useRef<OscillatorNode | null>(null);

  useEffect(() => {
    if (zone === "A") {
      setVisible(true);
      playAlert();
    } else {
      setVisible(false);
      stopAlert();
    }
  }, [zone]);

  const playAlert = () => {
    try {
      const ctx = new AudioContext();
      audioCtxRef.current = ctx;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "square";
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      osc.frequency.setValueAtTime(660, ctx.currentTime + 0.3);
      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      oscillatorRef.current = osc;
    } catch (_) {}
  };

  const stopAlert = () => {
    try {
      oscillatorRef.current?.stop();
      audioCtxRef.current?.close();
    } catch (_) {}
  };

  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center"
      style={{
        background: "rgba(220,0,0,0.92)",
        animation: "pulse-alert 0.8s ease-in-out infinite",
      }}
    >
      <style>{`
        @keyframes pulse-alert {
          0%,100% { opacity: 0.88; }
          50%      { opacity: 1.0; }
        }
      `}</style>

      <div className="text-white text-center select-none">
        <div className="text-9xl mb-6">⛔</div>
        <div className="text-6xl font-black tracking-widest mb-4">
          ZONE A — FULL STOP
        </div>
        <div className="text-2xl font-semibold mb-2">
          Human detected within 1.5 m
        </div>
        <div className="text-lg opacity-80">
          ISO/TS 15066 — Speed &amp; Separation Monitoring
        </div>
        <div className="text-lg opacity-80 mt-1">
          Auto-dismiss when human exits Zone A
        </div>
      </div>

      <button
        onClick={() => { setVisible(false); stopAlert(); onDismiss?.(); }}
        className="mt-10 px-8 py-3 bg-white text-red-700 font-bold rounded-xl
                   text-lg hover:bg-red-100 transition"
      >
        Override (Manual)
      </button>
    </div>
  );
}
