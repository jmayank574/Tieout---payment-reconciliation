import type { ExceptionFilters } from '../../api/types';

const STATUS_VIEWS = [
  { label: 'Needs review', key: 'queue',       statuses: [] },
  { label: 'Resolved',     key: 'resolved',    statuses: ['resolved'] },
  { label: 'Written off',  key: 'written_off', statuses: ['written_off'] },
  { label: 'Flagged',      key: 'flagged',     statuses: ['flagged'] },
  { label: 'All',          key: 'all',         statuses: ['needs_review', 'flagged', 'partially_resolved', 'resolved', 'written_off', 'matched'] },
];

const MATCH_TYPES = [
  { value: '', label: 'All types' },
  { value: 'exact', label: 'Exact' },
  { value: 'fuzzy', label: 'Fuzzy' },
  { value: 'many_to_one', label: 'Many → 1' },
  { value: 'one_to_many', label: '1 → Many' },
  { value: 'reversal', label: 'Reversal' },
  { value: 'unmatched', label: 'Unmatched' },
];

const SORT_OPTIONS = [
  { value: 'amount_desc', label: 'Largest first' },
  { value: 'confidence_asc', label: 'Worst confidence' },
  { value: 'date_asc', label: 'Oldest first' },
];

function statusViewKey(status: string[]): string {
  if (status.length === 0) return 'queue';
  if (status.length === 1) return status[0];
  return 'all';
}

interface FilterBarProps {
  filters: ExceptionFilters;
  onChange: (patch: Partial<ExceptionFilters>) => void;
}

const sel =
  'rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 shadow-sm ' +
  'focus:outline-none focus:ring-2 focus:ring-[#0C7785]/30 focus:border-[#0C7785] transition-colors';

const inp =
  'w-24 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-sm text-gray-700 shadow-sm ' +
  'focus:outline-none focus:ring-2 focus:ring-[#0C7785]/30 focus:border-[#0C7785] ' +
  'placeholder:text-gray-400 transition-colors';

export function FilterBar({ filters, onChange }: FilterBarProps) {
  const currentKey = statusViewKey(filters.status);
  const hasSecondary = !!(filters.match_type || filters.amount_min || filters.amount_max);

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      {/* Status */}
      <select
        value={currentKey}
        onChange={e => {
          const view = STATUS_VIEWS.find(v => v.key === e.target.value)!;
          onChange({ status: view.statuses, page: 1 });
        }}
        className={sel}
        aria-label="Status view"
      >
        {STATUS_VIEWS.map(v => (
          <option key={v.key} value={v.key}>{v.label}</option>
        ))}
      </select>

      {/* Match type */}
      <select
        value={filters.match_type}
        onChange={e => onChange({ match_type: e.target.value, page: 1 })}
        className={sel}
        aria-label="Match type"
      >
        {MATCH_TYPES.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* Sort */}
      <select
        value={filters.sort}
        onChange={e => onChange({ sort: e.target.value, page: 1 })}
        className={sel}
        aria-label="Sort order"
      >
        {SORT_OPTIONS.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* Amount range */}
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-gray-400">$</span>
        <input
          type="number"
          min="0"
          step="0.01"
          placeholder="Min"
          value={filters.amount_min}
          onChange={e => onChange({ amount_min: e.target.value, page: 1 })}
          className={inp}
          aria-label="Minimum amount"
          style={{ fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums' }}
        />
        <span className="text-xs text-gray-300">–</span>
        <input
          type="number"
          min="0"
          step="0.01"
          placeholder="Max"
          value={filters.amount_max}
          onChange={e => onChange({ amount_max: e.target.value, page: 1 })}
          className={inp}
          aria-label="Maximum amount"
          style={{ fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums' }}
        />
      </div>

      {hasSecondary && (
        <button
          onClick={() => onChange({ match_type: '', amount_min: '', amount_max: '', page: 1 })}
          className="text-xs text-gray-400 hover:text-gray-700 underline underline-offset-2 transition-colors"
        >
          Clear
        </button>
      )}
    </div>
  );
}
