import { motion } from 'framer-motion';
import type { CashPositionResponse } from '../../api/types';
import { Money } from '../shared/Money';
import { SkeletonCard } from '../shared/Skeleton';

interface Props {
  data: CashPositionResponse | undefined;
  isLoading: boolean;
}

function StatCard({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <motion.div layout className="rounded-xl border border-gray-200 bg-white px-5 py-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wider text-gray-500">{label}</p>
      <div className="mt-2">{value}</div>
      {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
    </motion.div>
  );
}

export function CashStatStrip({ data, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    );
  }
  if (!data) return null;

  const { summary } = data;
  const groupCount = data.groups.length;
  const shortfallCount = summary.groups_in_shortfall;
  const watchCount = data.groups.filter(g => g.coverage_status === 'watch').length;

  return (
    <div className="grid grid-cols-3 gap-4">
      <StatCard
        label="Total funded (cleared)"
        value={
          <Money
            value={summary.total_funded}
            className={`text-2xl font-semibold ${parseFloat(summary.total_funded) < 0 ? 'text-red-600' : 'text-gray-900'}`}
            showSign={true}
          />
        }
        sub={`net of ${groupCount} groups — bank-confirmed`}
      />
      <StatCard
        label="Pending claims liability"
        value={
          <Money
            value={summary.total_pending_liability}
            className="text-2xl font-semibold text-gray-900"
          />
        }
        sub="uncleared claim_payment entries"
      />
      <StatCard
        label="Coverage alerts"
        value={
          <p
            className={`text-2xl font-semibold leading-none ${shortfallCount > 0 ? 'text-red-600' : watchCount > 0 ? 'text-amber-600' : 'text-emerald-700'}`}
          >
            {shortfallCount > 0
              ? `${shortfallCount} shortfall${shortfallCount > 1 ? 's' : ''}`
              : watchCount > 0
              ? `${watchCount} watch`
              : 'All clear'}
          </p>
        }
        sub={`${watchCount} watch · ${groupCount - shortfallCount - watchCount} healthy`}
      />
    </div>
  );
}
