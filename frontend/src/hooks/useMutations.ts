import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFakeMutation, apiPost } from '../api/client';
import { useDataSource } from '../context/DataSourceContext';
import type { AllocationItem } from '../api/types';

function useActionMutation(
  action: (bankEventId: string, body: Record<string, unknown>) => Promise<unknown>,
  onSuccess?: (bankEventId: string) => void,
  onError?: (msg: string) => void,
) {
  const qc = useQueryClient();

  return useMutation({
    mutationFn: ({ bankEventId, body }: { bankEventId: string; body: Record<string, unknown> }) =>
      action(bankEventId, body),
    onSuccess: (_data, { bankEventId }) => {
      void qc.invalidateQueries({ queryKey: ['exceptions'] });
      void qc.invalidateQueries({ queryKey: ['exception', bankEventId] });
      void qc.invalidateQueries({ queryKey: ['stats'] });
      void qc.invalidateQueries({ queryKey: ['audit', bankEventId] });
      onSuccess?.(bankEventId);
    },
    onError: (err: Error) => {
      onError?.(err.message);
    },
  });
}

export function useAccept(
  onSuccess?: (id: string) => void,
  onError?: (msg: string) => void,
) {
  const { isLive } = useDataSource();
  return useActionMutation(
    (id, body) =>
      isLive ? apiPost(`/exceptions/${id}/accept`, body) : apiFakeMutation(),
    onSuccess,
    onError,
  );
}

export function useMatch(
  onSuccess?: (id: string) => void,
  onError?: (msg: string) => void,
) {
  const { isLive } = useDataSource();
  return useActionMutation(
    (id, body) =>
      isLive ? apiPost(`/exceptions/${id}/match`, body) : apiFakeMutation(),
    onSuccess,
    onError,
  );
}

export function useSplit(
  onSuccess?: (id: string) => void,
  onError?: (msg: string) => void,
) {
  const { isLive } = useDataSource();
  return useActionMutation(
    (id, body) =>
      isLive ? apiPost(`/exceptions/${id}/split`, body) : apiFakeMutation(),
    onSuccess,
    onError,
  );
}

export function useWriteOff(
  onSuccess?: (id: string) => void,
  onError?: (msg: string) => void,
) {
  const { isLive } = useDataSource();
  return useActionMutation(
    (id, body) =>
      isLive ? apiPost(`/exceptions/${id}/write-off`, body) : apiFakeMutation(),
    onSuccess,
    onError,
  );
}

export function useFlag(
  onSuccess?: (id: string) => void,
  onError?: (msg: string) => void,
) {
  const { isLive } = useDataSource();
  return useActionMutation(
    (id, body) =>
      isLive ? apiPost(`/exceptions/${id}/flag`, body) : apiFakeMutation(),
    onSuccess,
    onError,
  );
}

export function useReopen(
  onSuccess?: (id: string) => void,
  onError?: (msg: string) => void,
) {
  const { isLive } = useDataSource();
  return useActionMutation(
    (id, body) =>
      isLive ? apiPost(`/exceptions/${id}/reopen`, body) : apiFakeMutation(),
    onSuccess,
    onError,
  );
}

// Convenience typed wrappers
export type { AllocationItem };
