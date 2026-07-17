import { useEffect, useState } from 'react'

export default function HealthGauge({ score, label, colorClass }) {
  const radius = 54
  const circumference = 2 * Math.PI * radius
  const isPending = label === 'Pending'
  const displayScore = isPending ? '--' : score
  const targetOffset = isPending ? circumference : circumference - (Math.min(score, 100) / 100) * circumference
  const [offset, setOffset] = useState(circumference)

  useEffect(() => {
    if (isPending) {
      setOffset(circumference)
      return
    }
    const raf = requestAnimationFrame(() => setOffset(targetOffset))
    return () => cancelAnimationFrame(raf)
  }, [circumference, isPending, targetOffset])

  return (
    <div className={`health-gauge ${colorClass} ${isPending ? 'gauge-pending' : ''}`}>
      <svg viewBox="0 0 140 140" className="gauge-svg">
        <circle cx="70" cy="70" r={radius} className="gauge-track" />
        <circle
          cx="70" cy="70" r={radius}
          className="gauge-fill"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="gauge-center">
        <span className="gauge-score">{displayScore}</span>
        <span className="gauge-label">{label}</span>
      </div>
    </div>
  )
}
