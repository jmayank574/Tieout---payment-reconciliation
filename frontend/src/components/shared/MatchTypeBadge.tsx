const TYPE_CONFIG: Record<string, { label: string; className: string }> = {
  exact: { label: 'Exact', className: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200' },
  fuzzy: { label: 'Fuzzy', className: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200' },
  many_to_one: { label: 'Many→1', className: 'bg-violet-50 text-violet-700 ring-1 ring-violet-200' },
  one_to_many: { label: '1→Many', className: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200' },
  reversal: { label: 'Reversal', className: 'bg-orange-50 text-orange-700 ring-1 ring-orange-200' },
  unmatched: { label: 'Unmatched', className: 'bg-red-50 text-red-600 ring-1 ring-red-200' },
  split: { label: 'Split', className: 'bg-sky-50 text-sky-700 ring-1 ring-sky-200' },
  manual: { label: 'Manual', className: 'bg-gray-100 text-gray-600 ring-1 ring-gray-200' },
};

interface MatchTypeBadgeProps {
  matchType: string | null;
  className?: string;
}

export function MatchTypeBadge({ matchType, className = '' }: MatchTypeBadgeProps) {
  const type = matchType ?? 'unmatched';
  const config = TYPE_CONFIG[type] ?? { label: type, className: 'bg-gray-100 text-gray-500 ring-1 ring-gray-200' };

  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${config.className} ${className}`}
    >
      {config.label}
    </span>
  );
}
