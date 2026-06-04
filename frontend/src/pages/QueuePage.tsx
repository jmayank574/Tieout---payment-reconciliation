import { useState } from 'react';
import type { ExceptionFilters } from '../api/types';
import { ExceptionDrawer } from '../components/drawer/ExceptionDrawer';
import { FilterBar } from '../components/queue/FilterBar';
import { ExceptionTable } from '../components/queue/ExceptionTable';
import { StatStrip } from '../components/queue/StatStrip';
import { ToastList } from '../components/shared/Toast';
import { useExceptions } from '../hooks/useExceptions';
import { useStats } from '../hooks/useStats';
import { useToast } from '../hooks/useToast';

const DEFAULT_FILTERS: ExceptionFilters = {
  match_type: '',
  status: [],
  sort: 'amount_desc',
  amount_min: '',
  amount_max: '',
  page: 1,
};

export function QueuePage() {
  const [filters, setFilters] = useState<ExceptionFilters>(DEFAULT_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { toasts, push, dismiss } = useToast();

  const { data, isLoading } = useExceptions(filters);
  const { data: stats } = useStats();

  const queueTotal = stats
    ? (stats.by_status.needs_review ?? 0) +
      (stats.by_status.flagged ?? 0) +
      (stats.by_status.partially_resolved ?? 0)
    : null;

  function patchFilters(patch: Partial<ExceptionFilters>) {
    setFilters(prev => ({ ...prev, ...patch }));
  }

  function handleSelect(id: string) {
    setSelectedId(prev => (prev === id ? null : id));
  }

  return (
    <>
      <div className="space-y-6">
        {/* Stat strip */}
        <StatStrip />

        {/* Header */}
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Exception queue</h1>
          {data && (
            <p className="mt-0.5 text-sm text-gray-500">
              {filters.status.length === 0 && queueTotal != null
                ? `Showing ${data.items.length} of ${queueTotal} in queue`
                : `${data.total} ${filters.status.length === 1 ? filters.status[0].replace('_', ' ') : 'total'}`}
            </p>
          )}
        </div>

        {/* Single-row filter strip */}
        <FilterBar filters={filters} onChange={patchFilters} />

        {/* Table */}
        <ExceptionTable
          data={data}
          isLoading={isLoading}
          selectedId={selectedId}
          onSelect={handleSelect}
          filters={filters}
          onPageChange={page => patchFilters({ page })}
        />
      </div>

      {/* Detail drawer */}
      <ExceptionDrawer
        selectedId={selectedId}
        onClose={() => setSelectedId(null)}
        onToast={push}
      />

      {/* Toast stack */}
      <ToastList toasts={toasts} onDismiss={dismiss} />
    </>
  );
}
