export function HealthBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-400 text-sm">—</span>
  const cls =
    score < 40
      ? 'bg-red-100 text-red-700'
      : score <= 70
      ? 'bg-yellow-100 text-yellow-700'
      : 'bg-green-100 text-green-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {score}
    </span>
  )
}
