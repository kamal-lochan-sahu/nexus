'use client'
interface Props { onDismiss?: () => void }

export default function SafetyAlert({ onDismiss }: Props) {
  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(239,68,68,.15)',
      border:'2px solid var(--danger)', zIndex:1000,
      display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
      backdropFilter:'blur(4px)', animation:'dangerPulse 1s ease-in-out infinite' }}>
      <p style={{ fontFamily:'var(--font-mono)', fontSize:'3rem', fontWeight:900,
        color:'var(--danger)', letterSpacing:'.3em', marginBottom:12 }}>
        ⚠ DANGER
      </p>
      <p style={{ fontFamily:'var(--font-mono)', fontSize:16, color:'var(--text-primary)', marginBottom:24 }}>
        Safety zone violation detected — E-STOP armed
      </p>
      {onDismiss && (
        <button onClick={onDismiss}
          style={{ padding:'10px 24px', background:'var(--danger)', border:'none',
            color:'#fff', fontFamily:'var(--font-mono)', fontSize:12, fontWeight:700,
            letterSpacing:'.1em', cursor:'pointer', borderRadius:3 }}>
          ACKNOWLEDGE
        </button>
      )}
    </div>
  )
}
