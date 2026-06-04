import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { getMockAudit } from '../api/mock';
import type { AuditEvent } from '../api/types';
import { useDataSource } from '../context/DataSourceContext';

export function useAudit(bankEventId: string | null) {
  const { isLive } = useDataSource();

  return useQuery<AuditEvent[]>({
    queryKey: ['audit', bankEventId],
    queryFn: () =>
      isLive
        ? apiGet<AuditEvent[]>(`/audit/${bankEventId}`)
        : Promise.resolve(getMockAudit(bankEventId!)),
    enabled: bankEventId != null,
    staleTime: 60_000,
    retry: false,
  });
}
