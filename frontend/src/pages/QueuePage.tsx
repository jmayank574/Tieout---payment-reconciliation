import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { apiGet } from '../api/client';
import { filterMockExceptions, MOCK_EXCEPTIONS } from '../api/mock';
import type { ExceptionFilters, ExceptionList } from '../api/types';
import { AlertBanner } from '../components/queue/AlertBanner';
import { ExceptionDrawer } from '../components/drawer/ExceptionDrawer';
import { FilterBar } from '../components/queue/FilterBar';
import { ExceptionTable } from '../components/queue/ExceptionTable';
import { StatStrip } from '../components/queue/StatStrip';
import { ToastList } from '../components/shared/Toast';
import { useCashPosition } from '../hooks/useCashPosition';
import { useDataSource } from '../context/DataSourceContext';
import { useExceptions } from '../hooks/useExceptions';
import { useStats } from '../hooks/useStats';
import { useStaleAlerts } from '../hooks/useStaleAlerts';
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
  const [searchParams, setSearchParams] = useSearchParams();
  const { isLive } = useDataSource();

  // Initialise filters from URL params (set by cash-position drill-down)
  const [filters, setFilters] = useState<ExceptionFilters>(() => ({
    ...DEFAULT_FILTERS,
    group_id:   searchParams.get('group_id')   ?? undefined,
    group_name: searchParams.get('group_name') ?? undefined,
  }));

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { toasts, push, dismiss } = useToast();

  const { data, isLoading } = useExceptions(filters);
  const { data: stats } = useStats();
  const { data: cpData } = useCashPosition();
  const staleAlert = useStaleAlerts();

  // Sync URL when group filter changes so back-button works
  useEffect(() => {
    const next = new URLSearchParams();
    if (filters.group_id)   next.set('group_id',   filters.group_id);
    if (filters.group_name) next.set('group_name', filters.group_name);
    setSearchParams(next, { replace: true });
  }, [filters.group_id, filters.group_name, setSearchParams]);

  const groups = cpData?.groups.map(g => ({ id: g.group_id, name: g.group_name })) ?? [];

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

  // ── CSV export ─────────────────────────────────────────────────────────────
  async function downloadCsv() {
    let items: ExceptionList['items'];

    if (!isLive) {
      const result = filterMockExceptions(MOCK_EXCEPTIONS, {
        match_type: filters.match_type || undefined,
        status: filters.status.length > 0 ? filters.status : undefined,
        sort: filters.sort,
        amount_min: filters.amount_min || undefined,
        amount_max: filters.amount_max || undefined,
        group_id: filters.group_id || undefined,
        page: 1,
        page_size: 1000,
      });
      items = result.items;
    } else {
      const params = new URLSearchParams();
      if (filters.match_type) params.set('match_type', filters.match_type);
      if (filters.amount_min) params.set('amount_min', filters.amount_min);
      if (filters.amount_max) params.set('amount_max', filters.amount_max);
      if (filters.group_id)   params.set('group_id', filters.group_id);
      params.set('sort', filters.sort);
      params.set('page', '1');
      params.set('page_size', '1000');
      filters.status.forEach(s => params.append('status', s));
      const qs = params.toString();
      const result = await apiGet<ExceptionList>(`/exceptions${qs ? `?${qs}` : ''}`);
      items = result.items;
    }

    const today = new Date().toISOString().slice(0, 10);
    const header = ['Bank Event ID', 'Posted Date', 'Amount', 'Direction', 'Descriptor', 'Type', 'Confidence', 'Status', 'Bank Account ID'];
    const rows = items.map(e => [
      e.bank_event_id,
      e.posted_date,
      e.amount,
      e.direction,
      `"${(e.descriptor ?? '').replace(/"/g, '""')}"`,
      e.match_type ?? '',
      e.confidence ?? '',
      e.status,
      e.bank_account_id,
    ]);

    const csv = [header.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tieout-exceptions-${today}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <div className="space-y-6">
        {/* Stat strip */}
        <StatStrip />

        {/* Stale high-value alert */}
        {staleAlert && staleAlert.count > 0 && (
          <AlertBanner alert={staleAlert} />
        )}

        {/* Header */}
        <div>
          <h1 className="text-lg font-semibold text-gray-900">
            Exception queue
            {filters.group_name && (
              <span className="ml-2 text-sm font-normal text-[#0C7785]">
                · {filters.group_name}
              </span>
            )}
          </h1>
          {data && (
            <p className="mt-0.5 text-sm text-gray-500">
              {filters.status.length === 0 && !filters.group_id && queueTotal != null
                ? `Showing ${data.items.length} of ${queueTotal} in queue`
                : `${data.total} ${filters.status.length === 1 ? filters.status[0].replace('_', ' ') : 'total'}`}
            </p>
          )}
        </div>

        {/* Single-row filter strip */}
        <FilterBar
          filters={filters}
          onChange={patchFilters}
          groups={groups}
          onDownloadCsv={downloadCsv}
        />

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
