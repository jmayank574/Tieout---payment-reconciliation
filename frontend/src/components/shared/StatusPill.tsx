const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  needs_review: { label: 'Needs review', className: 'bg-[#E0F4F6] text-[#0C7785]' },
  flagged: { label: 'Flagged', className: 'bg-amber-50 text-amber-700' },
  partially_resolved: { label: 'Partial', className: 'bg-sky-50 text-sky-700' },
  resolved: { label: 'Resolved', className: 'bg-emerald-50 text-emerald-700' },
  written_off: { label: 'Written off', className: 'bg-gray-100 text-gray-500' },
  matched: { label: 'Matched', className: 'bg-emerald-50 text-emerald-700' },
  pending: { label: 'Pending', className: 'bg-gray-100 text-gray-500' },
};

interface StatusPillProps {
  status: string;
  className?: string;
}

export function StatusPill({ status, className = '' }: StatusPillProps) {
  const config = STATUS_CONFIG[status] ?? { label: status, className: 'bg-gray-100 text-gray-500' };

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${config.className} ${className}`}
    >
      {config.label}
    </span>
  );
}
