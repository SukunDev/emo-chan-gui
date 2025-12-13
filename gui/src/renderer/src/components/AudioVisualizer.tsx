export function AudioVisualizer({
  amplitude = 0,
  peak = 0,
  rms = 0
}: {
  amplitude?: number
  peak?: number
  rms?: number
}):React.JSX.Element {
  const bars = [
    amplitude * 100,
    rms * 100,
    peak * 100
  ]

  return (
    <div className="flex items-end gap-2 h-16">
      {bars.map((h, i) => (
        <div
          key={i}
          className="w-3 rounded-sm bg-primary transition-all duration-75"
          style={{ height: `${Math.min(h, 100)}%` }}
        />
      ))}
    </div>
  )
}
