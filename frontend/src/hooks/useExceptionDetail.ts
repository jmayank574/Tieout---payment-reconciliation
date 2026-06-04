import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { getMockDetail } from '../api/mock';
import type { ExceptionDetail } from '../api/types';
import { useDataSource } from '../context/DataSourceContext';

export function useExceptionDetail(bankEventId: string | null) {
  const { isLive } = useDataSource();

  return useQuery<ExceptionDetail>({
    queryKey: ['exception', bankEventId],
    queryFn: () =>
      isLive
        ? apiGet<ExceptionDetail>(`/exceptions/${bankEventId}`)
        : Promise.resolve(getMockDetail(bankEventId!)),
    enabled: bankEventId != null,
    staleTime: 30_000,
    retry: false,
  });
}
