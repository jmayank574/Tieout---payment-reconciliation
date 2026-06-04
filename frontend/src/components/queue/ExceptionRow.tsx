import { motion } from 'framer-motion';
import type { ExceptionSummary } from '../../api/types';
import { ConfidenceBar } from '../shared/ConfidenceBar';
import { MatchTypeBadge } from '../shared/MatchTypeBadge';
import { Money } from '../shared/Money';
import { StatusPill } from '../shared/StatusPill';

function age(dateStr: string): string {
  const posted = new Date(dateStr);
  const now = new Date();
  const days = Math.floor((now.getTime() - posted.getTime()) / 86_400_000);
  if (days === 0) return 'Today';
  if (days === 1) return '1d';
  return `${days}d`;
}

function ageClass(dateStr: string): string {
  const days = Math.floor((new Date().getTime() - new Date(dateStr).getTime()) / 86_400_000);
  if (days > 14) return 'text-red-600 font-medium';
  if (days > 7) return 'text-amber-700';
  return 'text-gray-500';
}

interface ExceptionRowProps {
  item: ExceptionSummary;
  isSelected: boolean;
  onClick: () => void;
}

export function ExceptionRow({ item, isSelected, onClick }: ExceptionRowProps) {
  return (
    <motion.tr
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.15 }}
      onClick={onClick}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } }}
      tabIndex={0}
      role="row"
      aria-selected={isSelected}
      className={`cursor-pointer border-b border-gray-100 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#0C7785]/40 ${
        isSelected
          ? 'bg-[#F0FAFB]'
          : 'hover:bg-gray-50'
      }`}
    >
      {/* Descriptor + account */}
      <td className="px-4 py-3">
        <p className="text-sm font-medium text-gray-900 truncate max-w-xs">
          {item.descriptor ?? <span className="text-gray-400 italic">No descriptor</span>}
        </p>
        <p
          className="mt-0.5 text-[11px] text-gray-400 truncate"
          style={{ fontFamily: '"JetBrains Mono", monospace' }}
        >
          {item.bank_event_id.slice(0, 8)}…
        </p>
      </td>

      {/* Amount */}
      <td className="px-4 py-3 text-right">
        <Money
          value={item.amount}
          className={`text-sm ${item.direction === 'credit' ? 'text-emerald-700' : 'text-gray-900'}`}
        />
        <p className="mt-0.5 text-[11px] text-gray-400 text-right">
          {item.direction}
        </p>
      </td>

      {/* Match type */}
      <td className="px-4 py-3">
        <MatchTypeBadge matchType={item.match_type} />
      </td>

      {/* Confidence */}
      <td className="px-4 py-3">
        {item.match_type === 'unmatched' ? (
          <span className="text-xs text-gray-400 italic">no match</span>
        ) : (
          <ConfidenceBar confidence={item.confidence} />
        )}
      </td>

      {/* Age */}
      <td className={`px-4 py-3 text-sm ${ageClass(item.posted_date)}`}>
        <span style={{ fontFamily: '"JetBrains Mono", monospace' }}>
          {age(item.posted_date)}
        </span>
      </td>

      {/* Status */}
      <td className="px-4 py-3">
        <StatusPill status={item.status} />
      </td>
    </motion.tr>
  );
}
