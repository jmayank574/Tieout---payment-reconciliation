import type { ExceptionDetail } from '../../api/types';
import { Money } from '../shared/Money';

interface FactRowProps {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}

function FactRow({ label, value, mono }: FactRowProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[11px] font-medium uppercase tracking-wider text-gray-400">{label}</dt>
      <dd
        className={`text-sm text-gray-900 ${mono ? 'tabular' : ''}`}
        style={mono ? { fontFamily: '"JetBrains Mono", monospace' } : {}}
      >
        {value}
      </dd>
    </div>
  );
}

interface BankEventFactsProps {
  detail: ExceptionDetail;
}

export function BankEventFacts({ detail }: BankEventFactsProps) {
  const be = detail.bank_event;

  return (
    <section>
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
        Bank event
      </h3>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 rounded-lg border border-gray-100 bg-gray-50/50 p-4">
        <FactRow
          label="Amount"
          value={
            <Money
              value={be.amount}
              className={`text-base font-semibold ${be.direction === 'credit' ? 'text-emerald-700' : 'text-gray-900'}`}
            />
          }
        />
        <FactRow label="Direction" value={be.direction} />
        <FactRow label="Posted date" value={be.posted_date} mono />
        <FactRow label="Bank reference" value={be.bank_reference ?? '—'} mono />
        <FactRow
          label="Descriptor"
          value={be.descriptor ?? <span className="italic text-gray-400">None</span>}
        />
        <FactRow
          label="Account ID"
          value={
            <span className="text-[11px]" style={{ fontFamily: '"JetBrains Mono", monospace' }}>
              {be.bank_account_id.slice(0, 8)}…
            </span>
          }
        />
      </dl>
    </section>
  );
}
