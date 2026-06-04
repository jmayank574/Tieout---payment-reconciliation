function confidenceColor(score: number): string {
  if (score < 0.45) return '#E05C30'; // orange-red — danger zone
  if (score < 0.72) return '#D97706'; // amber — uncertain
  return '#0C7785';                   // teal — settled
}

interface ConfidenceBarProps {
  confidence: string | null;
  showLabel?: boolean;
  className?: string;
}

export function ConfidenceBar({ confidence, showLabel = true, className = '' }: ConfidenceBarProps) {
  if (confidence == null) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <div className="h-1 w-10 rounded-full bg-gray-200" />
        {showLabel && (
          <span className="tabular text-xs text-gray-400" style={{ fontFamily: '"JetBrains Mono", monospace' }}>
            —
          </span>
        )}
      </div>
    );
  }

  const score = parseFloat(confidence);
  const pct = Math.round(score * 100);
  const color = confidenceColor(score);

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className="relative h-1.5 w-12 rounded-full bg-gray-200 overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-all duration-300"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      {showLabel && (
        <span
          className="tabular text-xs font-medium leading-none"
          style={{ color, fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums' }}
        >
          {pct}%
        </span>
      )}
    </div>
  );
}

export { confidenceColor };
