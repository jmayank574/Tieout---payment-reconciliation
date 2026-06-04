import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../api/client';
import { MOCK_CASH_POSITION, MOCK_GROUP_DETAIL } from '../api/mock';
import type { CashPositionResponse, GroupPositionDetail } from '../api/types';
import { useDataSource } from '../context/DataSourceContext';

export function useCashPosition() {
  const { isLive, checked } = useDataSource();

  return useQuery<CashPositionResponse>({
    queryKey: ['cash-position'],
    queryFn: () =>
      isLive
        ? apiGet<CashPositionResponse>('/cash-position')
        : Promise.resolve(MOCK_CASH_POSITION),
    enabled: checked,
    staleTime: 30_000,
    retry: false,
  });
}

export function useGroupPosition(groupId: string | null) {
  const { isLive, checked } = useDataSource();

  return useQuery<GroupPositionDetail>({
    queryKey: ['cash-position', groupId],
    queryFn: () =>
      isLive
        ? apiGet<GroupPositionDetail>(`/cash-position/${groupId}`)
        : Promise.resolve({ ...MOCK_GROUP_DETAIL, group_id: groupId ?? MOCK_GROUP_DETAIL.group_id }),
    enabled: checked && groupId !== null,
    staleTime: 30_000,
    retry: false,
  });
}
