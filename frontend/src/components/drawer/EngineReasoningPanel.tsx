import type { ExceptionDetail, LedgerEntry } from '../../api/types';
import { ConfidenceBar, confidenceColor } from '../shared/ConfidenceBar';
import { MatchTypeBadge } from '../shared/MatchTypeBadge';
import { Money } from '../shared/Money';

function LedgerEntryCard({ entry }: { entry: LedgerEntry }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium text-gray-700">
            {entry.entry_type.replace(/_/g, ' ')}
          </p>
          {entry.counterparty && (
            <p className="text-[11px] text-gray-500">{entry.counterparty}</p>
          )}
        </div>
        <Money
          value={entry.allocated_amount ?? entry.amount}
          className="text-sm font-semibold text-gray-900"
        />
      </div>
      <div className="flex items-center gap-4 text-[11px] text-gray-400">
        <span style={{ fontFamily: '"JetBrains Mono", monospace' }}>
          Expected {entry.expected_date}
        </span>
        {entry.reference && (
          <span style={{ fontFamily: '"JetBrains Mono", monospace' }}>
            ref {entry.reference}
          </span>
        )}
      </div>
    </div>
  );
}

interface EngineReasoningPanelProps {
  detail: ExceptionDetail;
}

export function EngineReasoningPanel({ detail }: EngineReasoningPanelProps) {
  const score = detail.confidence != null ? parseFloat(detail.confidence) : null;
  const color = score != null ? confidenceColor(score) : '#9CA3AF';
  const pct = score != null ? Math.round(score * 100) : null;

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Engine suggestion
        </h3>
        <div className="flex items-center gap-2">
          <MatchTypeBadge matchType={detail.match_type} />
          {pct != null && (
            <span
              className="text-sm font-semibold"
              style={{ color, fontFamily: '"JetBrains Mono", monospace' }}
            >
              {pct}%
            </span>
          )}
        </div>
      </div>

      {/* Confidence meter */}
      {score != null && (
        <div className="mb-4">
          <div className="relative h-2 w-full rounded-full bg-gray-100 overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
              style={{ width: `${Math.round(score * 100)}%`, backgroundColor: color }}
            />
          </div>
          <div className="mt-1.5 flex justify-between text-[10px]">
            <span className="text-gray-400">0%</span>
            <span className="text-gray-400">Uncertain</span>
            <span className="text-gray-400">100%</span>
          </div>
        </div>
      )}

      {/* Suggested ledger entries */}
      {detail.suggested_ledger_entries.length > 0 ? (
        <div className="space-y-2 mb-4">
          {detail.suggested_ledger_entries.map(le => (
            <LedgerEntryCard key={le.id} entry={le} />
          ))}
        </div>
      ) : (
        <div className="mb-4 rounded-lg border border-dashed border-gray-200 p-4 text-center">
          <p className="text-sm text-gray-400">No suggested ledger entry</p>
        </div>
      )}

      {/* Why uncertain — hero callout */}
      <div
        className="rounded-lg border-l-4 bg-amber-50 px-4 py-3"
        style={{ borderLeftColor: '#D97706' }}
      >
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-amber-700">
          Why uncertain
        </p>
        <p className="text-sm leading-relaxed text-amber-900">{detail.why_uncertain}</p>
      </div>
    </section>
  );
}
