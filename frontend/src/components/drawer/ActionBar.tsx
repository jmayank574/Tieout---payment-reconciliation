import { useState } from 'react';
import type { ExceptionDetail } from '../../api/types';
import {
  useAccept,
  useFlag,
  useMatch,
  useReopen,
  useSplit,
  useWriteOff,
} from '../../hooks/useMutations';
import { Button } from '../shared/Button';
import { SplitForm } from './SplitForm';

type ActiveModal = 'match' | 'split' | 'write_off' | 'flag' | null;

interface ActionBarProps {
  detail: ExceptionDetail;
  selectedCandidateIds: Set<string>;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
  onClose: () => void;
}

export function ActionBar({ detail, selectedCandidateIds, onSuccess, onError, onClose }: ActionBarProps) {
  const [modal, setModal] = useState<ActiveModal>(null);
  const [noteText, setNoteText] = useState('');

  const bankEventId = detail.bank_event_id;

  const handleSuccess = (msg: string) => {
    onSuccess(msg);
    onClose();
  };

  const accept = useAccept(
    () => handleSuccess('Exception accepted — marked resolved.'),
    onError,
  );

  const match = useMatch(
    () => handleSuccess('Manually matched and resolved.'),
    onError,
  );

  const split = useSplit(
    () => handleSuccess('Split allocation recorded.'),
    onError,
  );

  const writeOff = useWriteOff(
    () => handleSuccess('Exception written off.'),
    onError,
  );

  const flag = useFlag(
    () => handleSuccess('Exception flagged for follow-up.'),
    onError,
  );

  const reopen = useReopen(
    () => handleSuccess('Reopened for review.'),
    onError,
  );

  const isTerminal = ['resolved', 'written_off'].includes(detail.status);
  const isMatched = detail.status === 'matched';
  const busy = accept.isPending || match.isPending || split.isPending || writeOff.isPending || flag.isPending || reopen.isPending;

  if (isTerminal) {
    return (
      <div className="rounded-lg bg-gray-50 border border-gray-200 px-4 py-3 text-sm text-gray-500 text-center">
        This exception is <strong className="text-gray-700">{detail.status.replace('_', ' ')}</strong>
        {detail.resolved_by && ` by ${detail.resolved_by}`}
        {detail.resolved_at && ` on ${detail.resolved_at.slice(0, 10)}`}.
      </div>
    );
  }

  if (modal === 'split') {
    return (
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">Split allocation</p>
        <SplitForm
          bankAmount={detail.bank_event.amount}
          candidates={detail.candidates}
          isSubmitting={split.isPending}
          onSubmit={allocations => {
            split.mutate({
              bankEventId,
              body: { allocations, actor: 'operator' },
            });
          }}
          onCancel={() => setModal(null)}
        />
      </div>
    );
  }

  if (modal === 'write_off') {
    return (
      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Write-off reason</p>
        <textarea
          value={noteText}
          onChange={e => setNoteText(e.target.value)}
          placeholder="Explain why no ledger counterpart exists…"
          rows={3}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-none"
        />
        <div className="flex gap-2">
          <Button
            variant="danger"
            onClick={() => {
              if (!noteText.trim()) return;
              writeOff.mutate({ bankEventId, body: { reason: noteText.trim(), actor: 'operator' } });
            }}
            disabled={!noteText.trim() || writeOff.isPending}
          >
            {writeOff.isPending ? 'Writing off…' : 'Write off'}
          </Button>
          <Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button>
        </div>
      </div>
    );
  }

  if (modal === 'flag') {
    return (
      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Flag note</p>
        <textarea
          value={noteText}
          onChange={e => setNoteText(e.target.value)}
          placeholder="Add a note for follow-up…"
          rows={3}
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent resize-none"
        />
        <div className="flex gap-2">
          <Button
            variant="warning"
            onClick={() => {
              if (!noteText.trim()) return;
              flag.mutate({ bankEventId, body: { note: noteText.trim(), actor: 'operator' } });
            }}
            disabled={!noteText.trim() || flag.isPending}
          >
            {flag.isPending ? 'Flagging…' : 'Flag'}
          </Button>
          <Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Actions</p>

      <div className="flex flex-wrap gap-2">
        {/* Accept — primary happy path */}
        {!isMatched && (
          <Button
            variant="primary"
            onClick={() => accept.mutate({ bankEventId, body: { actor: 'operator' } })}
            disabled={busy}
          >
            {accept.isPending ? 'Accepting…' : 'Accept'}
          </Button>
        )}

        {/* Match with selected candidates */}
        {selectedCandidateIds.size > 0 && (
          <Button
            variant="secondary"
            onClick={() =>
              match.mutate({
                bankEventId,
                body: {
                  ledger_entry_ids: Array.from(selectedCandidateIds),
                  actor: 'operator',
                },
              })
            }
            disabled={busy}
          >
            {match.isPending ? 'Matching…' : `Match (${selectedCandidateIds.size})`}
          </Button>
        )}

        {/* Split */}
        {detail.candidates.length > 0 && (
          <Button variant="secondary" onClick={() => setModal('split')} disabled={busy}>
            Split
          </Button>
        )}

        {/* Write off */}
        <Button variant="danger" onClick={() => { setNoteText(''); setModal('write_off'); }} disabled={busy}>
          Write off
        </Button>

        {/* Flag */}
        <Button variant="secondary" onClick={() => { setNoteText(''); setModal('flag'); }} disabled={busy}>
          Flag
        </Button>

        {/* Reopen — only for matched status */}
        {isMatched && (
          <Button
            variant="secondary"
            onClick={() => reopen.mutate({ bankEventId, body: { actor: 'operator' } })}
            disabled={busy}
          >
            {reopen.isPending ? 'Reopening…' : 'Reopen'}
          </Button>
        )}
      </div>

      {detail.notes && (
        <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-xs text-gray-600">
          <span className="font-medium text-gray-500">Note: </span>{detail.notes}
        </div>
      )}
    </div>
  );
}
