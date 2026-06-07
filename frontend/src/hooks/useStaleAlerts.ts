import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { MOCK_EXCEPTIONS } from '../api/mock';
import type { ExceptionList } from '../api/types';
import { useDataSource } from '../context/DataSourceContext';

const ALERT_AMOUNT_THRESHOLD = 50_000;
const ALERT_AGE_DAYS = 14;

export interface StaleAlert {
  count: number;
  amountThreshold: number;
  ageDays: number;
}

function computeStale(items: { amount: string; posted_date: string }[]): number {
  const today = new Date();
  return items.filter(e => {
    const age = Math.floor((today.getTime() - new Date(e.posted_date).getTime()) / 86_400_000);
    return parseFloat(e.amount) >= ALERT_AMOUNT_THRESHOLD && age >= ALERT_AGE_DAYS;
  }).length;
}

export function useStaleAlerts(): StaleAlert | null {
  const { isLive, checked } = useDataSource();

  const { data } = useQuery<ExceptionList>({
    queryKey: ['stale-alerts'],
    queryFn: () => {
      if (!isLive) {
        const needs = MOCK_EXCEPTIONS.filter(e =>
          ['needs_review', 'flagged', 'partially_resolved'].includes(e.status)
        );
        return Promise.resolve({ items: needs, total: needs.length, page: 1, page_size: needs.length });
      }
      return apiGet<ExceptionList>(
        `/exceptions?status=needs_review&status=flagged&status=partially_resolved&page_size=500&sort=amount_desc`
      );
    },
    enabled: checked,
    staleTime: 60_000,
    retry: false,
  });

  if (!data) return null;
  const count = computeStale(data.items);
  return { count, amountThreshold: ALERT_AMOUNT_THRESHOLD, ageDays: ALERT_AGE_DAYS };
}
