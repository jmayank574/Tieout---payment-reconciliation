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
import { SplitForm } from './SplitForm';

type ActiveModal = 'match' | 'split' | 'write_off' | 'flag' | null;

interface ActionBarProps {
  detail: ExceptionDetail;
  selectedCandidateIds: Set<string>;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
  onClose: () => void;
}

const btnPrimary =
  'rounded-lg bg-[#0C7785] px-3.5 py-2 text-sm font-medium text-white hover:bg-[#0a6370] transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
const btnSecondary =
  'rounded-lg border border-gray-200 px-3.5 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
const btnDanger =
  'rounded-lg border border-red-200 px-3.5 py-2 text-sm font-medium text-red-700 hover:bg-red-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

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
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#0C7785]/30 focus:border-[#0C7785] resize-none"
        />
        <div className="flex gap-2">
          <button
            onClick={() => {
              if (!noteText.trim()) return;
              writeOff.mutate({ bankEventId, body: { reason: noteText.trim(), actor: 'operator' } });
            }}
            disabled={!noteText.trim() || writeOff.isPending}
            className={btnDanger}
          >
            {writeOff.isPending ? 'Writing off…' : 'Write off'}
          </button>
          <button onClick={() => setModal(null)} className={btnSecondary}>Cancel</button>
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
          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[#0C7785]/30 focus:border-[#0C7785] resize-none"
        />
        <div className="flex gap-2">
          <button
            onClick={() => {
              if (!noteText.trim()) return;
              flag.mutate({ bankEventId, body: { note: noteText.trim(), actor: 'operator' } });
            }}
            disabled={!noteText.trim() || flag.isPending}
            className="rounded-lg bg-amber-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-amber-700 transition-colors disabled:opacity-50"
          >
            {flag.isPending ? 'Flagging…' : 'Flag'}
          </button>
          <button onClick={() => setModal(null)} className={btnSecondary}>Cancel</button>
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
          <button
            onClick={() => accept.mutate({ bankEventId, body: { actor: 'operator' } })}
            disabled={busy}
            className={btnPrimary}
          >
            {accept.isPending ? 'Accepting…' : 'Accept'}
          </button>
        )}

        {/* Match with selected candidates */}
        {selectedCandidateIds.size > 0 && (
          <button
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
            className={btnSecondary}
          >
            {match.isPending ? 'Matching…' : `Match (${selectedCandidateIds.size})`}
          </button>
        )}

        {/* Split */}
        {detail.candidates.length > 0 && (
          <button onClick={() => setModal('split')} disabled={busy} className={btnSecondary}>
            Split
          </button>
        )}

        {/* Write off */}
        <button onClick={() => { setNoteText(''); setModal('write_off'); }} disabled={busy} className={btnDanger}>
          Write off
        </button>

        {/* Flag */}
        <button
          onClick={() => { setNoteText(''); setModal('flag'); }}
          disabled={busy}
          className={btnSecondary}
        >
          Flag
        </button>

        {/* Reopen — only for matched status */}
        {isMatched && (
          <button
            onClick={() => reopen.mutate({ bankEventId, body: { actor: 'operator' } })}
            disabled={busy}
            className={btnSecondary}
          >
            {reopen.isPending ? 'Reopening…' : 'Reopen'}
          </button>
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
