'use client'
import { useEffect, useRef, useState } from 'react'

interface Detection {
  label: string
  confidence: number
  bbox: [number, number, number, number]
  distance_estimate: string
}

interface VisionFeedProps {
  detections?: Detection[]
  wsUrl?: string
}

export default function VisionFeed({ detections = [], wsUrl }: VisionFeedProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [frameData, setFrameData] = useState<string | null>(null)
  const [fps, setFps] = useState(0)
  const frameCount = useRef(0)
  const lastTime = useRef(Date.now())

  // WebSocket for live frame
  useEffect(() => {
    if (!wsUrl) return
    const ws = new WebSocket(wsUrl)
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'frame') setFrameData(data.image)
    }
    return () => ws.close()
  }, [wsUrl])

  // Draw frame + bounding boxes on canvas
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // FPS counter
    frameCount.current++
    const now = Date.now()
    if (now - lastTime.current > 1000) {
      setFps(frameCount.current)
      frameCount.current = 0
      lastTime.current = now
    }

    if (frameData) {
      const img = new Image()
      img.onload = () => {
        ctx.drawImage(img, 0, 0, 640, 480)
        drawDetections(ctx, detections)
      }
      img.src = `data:image/jpeg;base64,${frameData}`
    } else {
      // Placeholder
      ctx.fillStyle = '#0a0a0a'
      ctx.fillRect(0, 0, 640, 480)
      ctx.fillStyle = '#1a1a2e'
      ctx.fillRect(10, 10, 620, 460)
      ctx.fillStyle = '#4ade80'
      ctx.font = '16px monospace'
      ctx.fillText('D455 Camera Feed — Waiting...', 200, 240)
      drawDetections(ctx, detections)
    }
  }, [frameData, detections])

  function drawDetections(ctx: CanvasRenderingContext2D, dets: Detection[]) {
    dets.forEach((d) => {
      const [x, y, w, h] = d.bbox
      const color = d.confidence > 0.7 ? '#4ade80' : '#facc15'
      ctx.strokeStyle = color
      ctx.lineWidth = 2
      ctx.strokeRect(x, y, w, h)
      ctx.fillStyle = color
      ctx.font = '12px monospace'
      ctx.fillText(`${d.label} ${(d.confidence * 100).toFixed(0)}% ${d.distance_estimate}`, x, y - 4)
    })
  }

  return (
    <div className="relative">
      <canvas ref={canvasRef} width={640} height={480}
        className="rounded-lg border border-green-500/30 bg-black" />
      <div className="absolute top-2 right-2 bg-black/70 px-2 py-1 rounded text-xs text-green-400 font-mono">
        D455 | {detections.length} obj
      </div>
    </div>
  )
}
