import { useState } from 'react';
import type { Candidate } from '../../api/types';
import { Money } from '../shared/Money';

interface SplitRow {
  ledger_entry_id: string;
  label: string;
  amount: string;
}

interface SplitFormProps {
  bankAmount: string;
  candidates: Candidate[];
  isSubmitting: boolean;
  onSubmit: (allocations: { ledger_entry_id: string; allocated_amount: string }[]) => void;
  onCancel: () => void;
}

export function SplitForm({ bankAmount, candidates, isSubmitting, onSubmit, onCancel }: SplitFormProps) {
  const bank = parseFloat(bankAmount);

  const [rows, setRows] = useState<SplitRow[]>(() =>
    candidates.slice(0, 3).map(c => ({
      ledger_entry_id: c.ledger_entry.id,
      label: `${c.ledger_entry.entry_type.replace(/_/g, ' ')} · ${c.ledger_entry.counterparty ?? c.ledger_entry.expected_date}`,
      amount: '',
    })),
  );

  const sum = rows.reduce((acc, r) => acc + (parseFloat(r.amount) || 0), 0);
  const remainder = bank - sum;
  const isOver = sum > bank + 0.001;
  const isFull = Math.abs(remainder) < 0.01;
  const isPartial = sum > 0 && sum < bank - 0.001;
  const canSubmit = sum > 0 && !isOver;

  function updateAmount(id: string, val: string) {
    setRows(prev => prev.map(r => (r.ledger_entry_id === id ? { ...r, amount: val } : r)));
  }

  function handleSubmit() {
    const allocations = rows
      .filter(r => parseFloat(r.amount) > 0)
      .map(r => ({ ledger_entry_id: r.ledger_entry_id, allocated_amount: r.amount }));
    onSubmit(allocations);
  }

  return (
    <div className="space-y-4">
      {rows.map(row => (
        <div key={row.ledger_entry_id} className="flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-gray-700 truncate">{row.label}</p>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-400">$</span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={row.amount}
              onChange={e => updateAmount(row.ledger_entry_id, e.target.value)}
              placeholder="0.00"
              className="w-28 rounded-md border border-gray-200 px-2.5 py-1.5 text-sm text-right focus:outline-none focus:ring-2 focus:ring-[#0C7785]/30 focus:border-[#0C7785]"
              style={{ fontFamily: '"JetBrains Mono", monospace', fontVariantNumeric: 'tabular-nums' }}
            />
          </div>
        </div>
      ))}

      {/* Live sum bar */}
      <div className={`rounded-lg px-3 py-2.5 text-sm ${
        isOver
          ? 'bg-red-50 border border-red-200'
          : isFull
          ? 'bg-emerald-50 border border-emerald-200'
          : isPartial
          ? 'bg-amber-50 border border-amber-200'
          : 'bg-gray-50 border border-gray-200'
      }`}>
        <div className="flex items-center justify-between">
          <span className={`font-medium text-xs ${
            isOver ? 'text-red-700' : isFull ? 'text-emerald-700' : isPartial ? 'text-amber-700' : 'text-gray-500'
          }`}>
            {isOver
              ? `Exceeds bank amount by $${(sum - bank).toFixed(2)}`
              : isFull
              ? 'Full allocation — ready to resolve'
              : isPartial
              ? `Partial — $${remainder.toFixed(2)} remainder will be tracked`
              : 'Enter amounts to allocate'}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-gray-400">Total</span>
            <span
              className={`text-sm font-semibold ${
                isOver ? 'text-red-600' : isFull ? 'text-emerald-600' : 'text-gray-900'
              }`}
              style={{ fontFamily: '"JetBrains Mono", monospace' }}
            >
              ${sum.toFixed(2)}
            </span>
            <span className="text-[11px] text-gray-400">of</span>
            <Money value={bankAmount} className="text-sm text-gray-600" />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={handleSubmit}
          disabled={!canSubmit || isSubmitting}
          className="flex-1 rounded-lg bg-[#0C7785] px-4 py-2 text-sm font-medium text-white hover:bg-[#0a6370] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? 'Submitting…' : isFull ? 'Resolve (split)' : 'Partial resolve'}
        </button>
        <button
          onClick={onCancel}
          className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
