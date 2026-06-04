import type { CoverageStatus } from '../../api/types';

const CONFIG: Record<CoverageStatus, { label: string; className: string }> = {
  healthy:   { label: 'Healthy',   className: 'bg-emerald-50 text-emerald-700' },
  watch:     { label: 'Watch',     className: 'bg-amber-50  text-amber-700'   },
  shortfall: { label: 'Shortfall', className: 'bg-red-50    text-red-700'     },
};

export function CoverageStatusPill({ status }: { status: CoverageStatus }) {
  const { label, className } = CONFIG[status] ?? CONFIG.healthy;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  );
}
