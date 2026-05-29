'use client'
import { useState } from 'react'

type PipelineStatus = 'idle' | 'processing' | 'executing' | 'complete' | 'error'

interface VLAStatusProps {
  status: PipelineStatus
  command?: string
  vlaOutput?: any
  totalMs?: number
  onCommand?: (cmd: string) => void
}

const STATUS_COLORS: Record<PipelineStatus, string> = {
  idle:       'text-gray-400 border-gray-600',
  processing: 'text-yellow-400 border-yellow-500',
  executing:  'text-blue-400 border-blue-500',
  complete:   'text-green-400 border-green-500',
  error:      'text-red-400 border-red-500',
}

const PIPELINE_STEPS = [
  { key: 'clip',   label: 'CLIP Encode',    icon: '👁' },
  { key: 'yolo',   label: 'YOLO Detect',    icon: '🎯' },
  { key: 'groq',   label: 'Groq Plan',      icon: '🧠' },
  { key: 'safety', label: 'Safety Check',   icon: '🛡' },
  { key: 'nav',    label: 'Navigate',       icon: '🤖' },
]

export default function VLAStatus({
  status = 'idle',
  command = '',
  vlaOutput,
  totalMs,
  onCommand,
}: VLAStatusProps) {
  const [inputCmd, setInputCmd] = useState('')

  const currentStep = {
    idle: -1, processing: 1, executing: 3, complete: 4, error: -1
  }[status]

  return (
    <div className="bg-gray-900 border border-green-500/20 rounded-lg p-4 font-mono text-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-green-400 font-bold">VLA Pipeline</h3>
        <span className={`px-2 py-0.5 rounded text-xs border ${STATUS_COLORS[status]}`}>
          {status.toUpperCase()}
          {totalMs ? ` ${(totalMs/1000).toFixed(1)}s` : ''}
        </span>
      </div>

      {/* Command Input */}
      <div className="mb-3 flex gap-2">
        <input
          className="flex-1 bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:border-green-500 focus:outline-none"
          placeholder="Find the yellow marker..."
          value={inputCmd}
          onChange={e => setInputCmd(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && onCommand) { onCommand(inputCmd); setInputCmd('') }}}
        />
        <button
          onClick={() => { if (onCommand && inputCmd) { onCommand(inputCmd); setInputCmd('') }}}
          className="px-3 py-1.5 bg-green-600 hover:bg-green-500 rounded text-xs text-white transition-colors"
        >
          Run
        </button>
      </div>

      {/* Pipeline Steps */}
      <div className="space-y-1 mb-3">
        {PIPELINE_STEPS.map((step, i) => (
          <div key={step.key} className={`flex items-center gap-2 px-2 py-1 rounded text-xs transition-all
            ${i < currentStep ? 'bg-green-500/10 text-green-400' :
              i === currentStep ? 'bg-yellow-500/10 text-yellow-400' : 'text-gray-600'}`}>
            <span>{step.icon}</span>
            <span>{step.label}</span>
            {i < currentStep && <span className="ml-auto">✓</span>}
            {i === currentStep && <span className="ml-auto animate-pulse">●</span>}
          </div>
        ))}
      </div>

      {/* VLA Output Summary */}
      {vlaOutput && (
        <div className="p-2 bg-gray-800 rounded text-xs space-y-1">
          <div className="flex justify-between">
            <span className="text-gray-500">Intent</span>
            <span className="text-cyan-400">{vlaOutput.intent}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Safety</span>
            <span className={vlaOutput.safety_check === 'clear' ? 'text-green-400' : 'text-red-400'}>
              {vlaOutput.safety_check}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Confidence</span>
            <span className="text-yellow-400">{(vlaOutput.confidence * 100).toFixed(0)}%</span>
          </div>
          {vlaOutput.plan?.[0] && (
            <div className="flex justify-between">
              <span className="text-gray-500">Action</span>
              <span className="text-green-300">{vlaOutput.plan[0].action}</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
