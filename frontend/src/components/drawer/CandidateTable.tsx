import type { Candidate } from '../../api/types';
import { Money } from '../shared/Money';

interface CandidateTableProps {
  candidates: Candidate[];
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
}

export function CandidateTable({ candidates, selectedIds, onToggle }: CandidateTableProps) {
  if (candidates.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-200 p-4 text-center">
        <p className="text-sm text-gray-400">No alternative candidates found</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-gray-200">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-100">
          <tr>
            <th className="w-8 px-3 py-2" />
            <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Ledger entry
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
              Amount
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Score
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Reasons
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {candidates.map(c => {
            const le = c.ledger_entry;
            const pct = Math.round(c.score * 100);
            const isSelected = selectedIds.has(le.id);

            return (
              <tr
                key={le.id}
                onClick={() => onToggle(le.id)}
                className={`cursor-pointer transition-colors ${
                  isSelected ? 'bg-[#F0FAFB]' : 'hover:bg-gray-50'
                }`}
              >
                <td className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => onToggle(le.id)}
                    onClick={e => e.stopPropagation()}
                    className="rounded border-gray-300 text-[#0C7785] focus:ring-[#0C7785]/30"
                    aria-label={`Select ${le.id}`}
                  />
                </td>
                <td className="px-3 py-2.5">
                  <p className="font-medium text-gray-900 text-xs">
                    {le.entry_type.replace(/_/g, ' ')}
                  </p>
                  <p className="text-[11px] text-gray-400" style={{ fontFamily: '"JetBrains Mono", monospace' }}>
                    {le.expected_date} · {le.counterparty ?? '—'}
                  </p>
                </td>
                <td className="px-3 py-2.5 text-right">
                  <Money value={le.amount} className="text-xs text-gray-900" />
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-1.5">
                    <div className="relative h-1 w-10 rounded-full bg-gray-200 overflow-hidden">
                      <div
                        className="absolute inset-y-0 left-0 rounded-full bg-[#0C7785]"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span
                      className="text-[11px] text-gray-600"
                      style={{ fontFamily: '"JetBrains Mono", monospace' }}
                    >
                      {pct}%
                    </span>
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <p className="text-[11px] text-gray-500">{c.score_reasons.join(' · ')}</p>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
