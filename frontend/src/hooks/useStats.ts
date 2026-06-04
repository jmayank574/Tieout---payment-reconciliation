import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { MOCK_STATS } from '../api/mock';
import type { Stats } from '../api/types';
import { useDataSource } from '../context/DataSourceContext';

export function useStats() {
  const { isLive, checked } = useDataSource();

  return useQuery<Stats>({
    queryKey: ['stats'],
    queryFn: () => isLive ? apiGet<Stats>('/exceptions/stats') : Promise.resolve(MOCK_STATS),
    enabled: checked,
    staleTime: 30_000,
    retry: false,
  });
}
