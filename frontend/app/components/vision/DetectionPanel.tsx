'use client'

interface Detection {
  label: string
  confidence: number
  bbox: [number, number, number, number]
  distance_estimate: string
  center?: [number, number]
}

interface DetectionPanelProps {
  detections: Detection[]
  sceneSummary?: string
  clipConfidence?: number
  targetFound?: boolean
}

export default function DetectionPanel({
  detections = [],
  sceneSummary = 'No scene data',
  clipConfidence = 0,
  targetFound = false,
}: DetectionPanelProps) {
  return (
    <div className="bg-gray-900 border border-green-500/20 rounded-lg p-4 font-mono text-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-green-400 font-bold">YOLO Detections</h3>
        <span className={`px-2 py-0.5 rounded text-xs ${targetFound ? 'bg-green-500/20 text-green-400' : 'bg-gray-700 text-gray-400'}`}>
          {targetFound ? '✓ TARGET FOUND' : 'SEARCHING'}
        </span>
      </div>

      {/* CLIP Scene Summary */}
      <div className="mb-3 p-2 bg-blue-500/10 border border-blue-500/20 rounded">
        <div className="text-blue-400 text-xs mb-1">CLIP Scene Analysis</div>
        <div className="text-gray-300 text-xs">{sceneSummary}</div>
        <div className="mt-1">
          <div className="text-gray-500 text-xs mb-1">Confidence: {(clipConfidence * 100).toFixed(1)}%</div>
          <div className="h-1.5 bg-gray-700 rounded">
            <div className="h-full bg-blue-400 rounded transition-all duration-300"
              style={{ width: `${clipConfidence * 100}%` }} />
          </div>
        </div>
      </div>

      {/* Detections Table */}
      {detections.length === 0 ? (
        <div className="text-gray-500 text-center py-4">No objects detected</div>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-gray-700">
              <th className="text-left pb-1">Label</th>
              <th className="text-right pb-1">Conf</th>
              <th className="text-right pb-1">Distance</th>
            </tr>
          </thead>
          <tbody>
            {detections.map((d, i) => (
              <tr key={i} className="border-b border-gray-800">
                <td className="py-1 text-green-300">{d.label}</td>
                <td className="text-right text-yellow-400">{(d.confidence * 100).toFixed(0)}%</td>
                <td className="text-right text-cyan-400">{d.distance_estimate}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
