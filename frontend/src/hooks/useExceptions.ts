import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { filterMockExceptions, MOCK_EXCEPTIONS } from '../api/mock';
import type { ExceptionFilters, ExceptionList } from '../api/types';
import { useDataSource } from '../context/DataSourceContext';

export function useExceptions(filters: ExceptionFilters) {
  const { isLive, checked } = useDataSource();

  return useQuery<ExceptionList>({
    queryKey: ['exceptions', filters],
    queryFn: () => {
      if (!isLive) {
        const result = filterMockExceptions(MOCK_EXCEPTIONS, {
          match_type: filters.match_type || undefined,
          status: filters.status.length > 0 ? filters.status : undefined,
          sort: filters.sort,
          amount_min: filters.amount_min || undefined,
          amount_max: filters.amount_max || undefined,
          page: filters.page,
          page_size: 20,
        });
        return Promise.resolve(result);
      }

      const params = new URLSearchParams();
      if (filters.match_type) params.set('match_type', filters.match_type);
      if (filters.amount_min) params.set('amount_min', filters.amount_min);
      if (filters.amount_max) params.set('amount_max', filters.amount_max);
      params.set('sort', filters.sort);
      params.set('page', String(filters.page));
      params.set('page_size', '20');
      filters.status.forEach(s => params.append('status', s));

      const qs = params.toString();
      return apiGet<ExceptionList>(`/exceptions${qs ? `?${qs}` : ''}`);
    },
    enabled: checked,
    staleTime: 15_000,
    retry: false,
    placeholderData: prev => prev,
  });
}
