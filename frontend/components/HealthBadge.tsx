export function HealthBadge({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <span style={{ color: 'var(--text-tertiary)' }} className="text-sm">
        —
      </span>
    )
  }

  const label = score >= 70 ? 'Healthy' : score >= 40 ? 'At Risk' : 'Urgent'
  const bgVar = score >= 70 ? '--green-subtle' : score >= 40 ? '--amber-subtle' : '--red-subtle'
  const textVar = score >= 70 ? '--green' : score >= 40 ? '--amber' : '--red'

  return (
    <span
      style={{
        background: `var(${bgVar})`,
        color: `var(${textVar})`,
      }}
      className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium"
    >
      {score} · {label}
    </span>
  )
}
