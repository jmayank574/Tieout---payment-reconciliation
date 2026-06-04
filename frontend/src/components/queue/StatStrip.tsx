import { motion } from 'framer-motion';
import { useStats } from '../../hooks/useStats';
import { SkeletonCard } from '../shared/Skeleton';

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
  warn?: boolean;
}

function StatCard({ label, value, sub, accent, warn }: StatCardProps) {
  return (
    <motion.div
      layout
      className="rounded-xl border border-gray-200 bg-white px-5 py-4 shadow-sm"
    >
      <p className="text-xs font-medium uppercase tracking-wider text-gray-500">{label}</p>
      <p
        className={`mt-2 text-2xl font-semibold leading-none ${
          accent ? 'text-[#0C7785]' : warn ? 'text-red-600' : 'text-gray-900'
        }`}
        style={
          typeof value === 'string' && value.startsWith('$')
            ? { fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums' }
            : {}
        }
      >
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
    </motion.div>
  );
}

export function StatStrip() {
  const { data: stats, isLoading } = useStats();

  if (isLoading) {
    return (
      <div className="grid grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    );
  }

  if (!stats) return null;

  const queueDepth =
    (stats.by_status.needs_review ?? 0) +
    (stats.by_status.flagged ?? 0) +
    (stats.by_status.partially_resolved ?? 0);

  const totalEx = stats.total_exceptions || 1;
  const autoMatchRate = Math.round(((stats.by_status.matched ?? 0) / totalEx) * 100);

  const amtNum = parseFloat(stats.total_unresolved_amount);
  const amtFormatted =
    '$' +
    new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(
      amtNum,
    );

  const oldestDays = stats.oldest_unresolved_days;

  return (
    <div className="grid grid-cols-4 gap-4">
      <StatCard
        label="Needs review"
        value={queueDepth}
        sub={`${stats.by_status.flagged ?? 0} flagged`}
        accent
      />
      <StatCard
        label="Unresolved total"
        value={amtFormatted}
        sub={`${queueDepth} open items`}
      />
      <StatCard
        label="Auto-match rate"
        value={`${autoMatchRate}%`}
        sub={`${stats.by_status.matched ?? 0} of ${totalEx} cleared`}
      />
      <StatCard
        label="Oldest open"
        value={oldestDays != null ? `${oldestDays}d` : '—'}
        sub="days since posted"
        warn={(oldestDays ?? 0) > 14}
      />
    </div>
  );
}
