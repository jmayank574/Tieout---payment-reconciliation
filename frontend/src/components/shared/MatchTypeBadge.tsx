const TYPE_CONFIG: Record<string, { label: string; className: string }> = {
  exact: { label: 'Exact', className: 'bg-emerald-50 text-emerald-700' },
  fuzzy: { label: 'Fuzzy', className: 'bg-amber-50 text-amber-700' },
  many_to_one: { label: 'Many→1', className: 'bg-violet-50 text-violet-700' },
  one_to_many: { label: '1→Many', className: 'bg-blue-50 text-blue-700' },
  reversal: { label: 'Reversal', className: 'bg-orange-50 text-orange-700' },
  unmatched: { label: 'Unmatched', className: 'bg-red-50 text-red-600' },
  split: { label: 'Split', className: 'bg-sky-50 text-sky-700' },
  manual: { label: 'Manual', className: 'bg-gray-100 text-gray-600' },
};

interface MatchTypeBadgeProps {
  matchType: string | null;
  className?: string;
}

export function MatchTypeBadge({ matchType, className = '' }: MatchTypeBadgeProps) {
  const type = matchType ?? 'unmatched';
  const config = TYPE_CONFIG[type] ?? { label: type, className: 'bg-gray-100 text-gray-500' };

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${config.className} ${className}`}
    >
      {config.label}
    </span>
  );
}
