import { AnimatePresence } from 'framer-motion';
import type { ExceptionFilters, ExceptionList } from '../../api/types';
import { EmptyState, SkeletonRow } from '../shared/Skeleton';
import { ExceptionRow } from './ExceptionRow';

interface PaginationProps {
  page: number;
  total: number;
  pageSize: number;
  onChange: (p: number) => void;
}

function Pagination({ page, total, pageSize, onChange }: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between border-t border-gray-100 px-4 py-3">
      <p className="text-xs text-gray-500">
        {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
      </p>
      <div className="flex items-center gap-1">
        <button
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          className="rounded px-2.5 py-1 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          ←
        </button>
        {Array.from({ length: totalPages }, (_, i) => i + 1)
          .filter(p => Math.abs(p - page) <= 2)
          .map(p => (
            <button
              key={p}
              onClick={() => onChange(p)}
              className={`rounded px-2.5 py-1 text-sm transition-colors ${
                p === page
                  ? 'bg-[#0C7785] text-white font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {p}
            </button>
          ))}
        <button
          disabled={page >= totalPages}
          onClick={() => onChange(page + 1)}
          className="rounded px-2.5 py-1 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          →
        </button>
      </div>
    </div>
  );
}

interface ExceptionTableProps {
  data: ExceptionList | undefined;
  isLoading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  filters: ExceptionFilters;
  onPageChange: (page: number) => void;
}

const TH_CLASS = 'px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider text-gray-500';

export function ExceptionTable({
  data,
  isLoading,
  selectedId,
  onSelect,
  filters,
  onPageChange,
}: ExceptionTableProps) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[700px]" role="grid">
          <thead className="border-b border-gray-100 bg-gray-50/60">
            <tr>
              <th className={TH_CLASS}>Bank event</th>
              <th className={`${TH_CLASS} text-right`}>Amount</th>
              <th className={TH_CLASS}>Type</th>
              <th className={TH_CLASS}>Confidence</th>
              <th className={TH_CLASS}>Age</th>
              <th className={TH_CLASS}>Status</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
            ) : data?.items.length === 0 ? (
              <EmptyState
                title="No exceptions match these filters"
                description="Try clearing the filters or switching sort order."
              />
            ) : (
              <AnimatePresence initial={false}>
                {data?.items.map(item => (
                  <ExceptionRow
                    key={item.bank_event_id}
                    item={item}
                    isSelected={item.bank_event_id === selectedId}
                    onClick={() => onSelect(item.bank_event_id)}
                  />
                ))}
              </AnimatePresence>
            )}
          </tbody>
        </table>
      </div>

      {data && (
        <Pagination
          page={filters.page}
          total={data.total}
          pageSize={data.page_size}
          onChange={onPageChange}
        />
      )}
    </div>
  );
}
