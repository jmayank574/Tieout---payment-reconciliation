import { AnimatePresence, motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useGroupPosition } from '../../hooks/useCashPosition';
import type { CashLedgerEntry } from '../../api/types';
import { Money } from '../shared/Money';
import { CoverageStatusPill } from './CoverageStatusPill';

interface Props {
  groupId: string | null;
  groupName?: string;
  onClose: () => void;
}

function EntryRow({ entry }: { entry: CashLedgerEntry }) {
  const isCredit = entry.direction === 'credit';
  return (
    <tr className="border-t border-gray-50 hover:bg-gray-50/50 transition-colors">
      <td className="py-2 pr-3 text-xs text-gray-500 capitalize">
        {entry.entry_type.replace(/_/g, ' ')}
      </td>
      <td className="py-2 pr-3 text-xs text-gray-400">{entry.expected_date}</td>
      <td className="py-2 pr-3 text-xs text-gray-500 max-w-[140px] truncate">
        {entry.counterparty ?? '—'}
      </td>
      <td className="py-2 text-right text-xs">
        <Money
          value={entry.amount}
          className={isCredit ? 'text-emerald-700' : 'text-gray-700'}
        />
        <span className={`ml-1 text-[10px] ${isCredit ? 'text-emerald-500' : 'text-gray-400'}`}>
          {isCredit ? 'CR' : 'DR'}
        </span>
      </td>
    </tr>
  );
}

export function CashGroupDrawer({ groupId, groupName, onClose }: Props) {
  const { data: detail, isLoading } = useGroupPosition(groupId);
  const navigate = useNavigate();

  return (
    <AnimatePresence>
      {groupId && (
        <>
          <motion.div
            key="cash-backdrop"
            className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            aria-hidden
          />

          <motion.aside
            key="cash-drawer"
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-[620px] flex-col bg-white shadow-2xl"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 32, stiffness: 320 }}
            role="dialog"
            aria-modal="true"
            aria-label="Group cash position detail"
          >
            {/* Header */}
            <div className="flex items-start justify-between border-b border-gray-100 px-6 py-4">
              {isLoading || !detail ? (
                <div className="animate-pulse space-y-2">
                  <div className="h-4 w-40 rounded bg-gray-200" />
                  <div className="h-7 w-28 rounded bg-gray-200" />
                </div>
              ) : (
                <div>
                  <div className="flex items-center gap-3">
                    <p className="text-xs text-gray-500">{detail.group_name}</p>
                    <button
                      onClick={() => {
                        onClose();
                        navigate(`/?group_id=${detail.group_id}&group_name=${encodeURIComponent(detail.group_name)}`);
                      }}
                      className="text-xs font-medium text-[#0C7785] hover:underline"
                    >
                      View exceptions →
                    </button>
                  </div>
                  <div className="mt-1 flex items-baseline gap-3">
                    <Money
                      value={detail.funded_balance}
                      showSign={true}
                      className={`text-2xl font-semibold ${parseFloat(detail.funded_balance) < 0 ? 'text-red-700' : 'text-gray-900'}`}
                    />
                    <CoverageStatusPill status={detail.coverage_status} />
                  </div>
                </div>
              )}
              <button
                onClick={onClose}
                className="ml-4 shrink-0 rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0C7785]"
                aria-label="Close"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
              {isLoading && (
                <div className="animate-pulse space-y-4">
                  {[80, 120, 200].map((h, i) => (
                    <div key={i} className="rounded-lg bg-gray-100" style={{ height: h }} />
                  ))}
                </div>
              )}

              {!isLoading && detail && (
                <>
                  {/* Key metrics */}
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { label: 'Funded balance', value: detail.funded_balance },
                      { label: 'Pending liability', value: detail.pending_claims_liability },
                      { label: 'Available to cover', value: detail.available_to_cover },
                    ].map(({ label, value }) => (
                      <div key={label} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                        <p className="text-[10px] font-medium uppercase tracking-wider text-gray-400">{label}</p>
                        <Money
                          value={value}
                          showSign={true}
                          className={`mt-1 block text-base font-semibold ${parseFloat(value) < 0 ? 'text-red-700' : 'text-gray-900'}`}
                        />
                      </div>
                    ))}
                  </div>

                  <div className="text-xs text-gray-400">
                    {detail.member_count} enrolled members
                  </div>

                  {/* Cleared entries */}
                  {detail.cleared_entries.length > 0 && (
                    <>
                      <div className="border-t border-gray-100" />
                      <section>
                        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                          Cleared entries
                          <span className="ml-1.5 font-normal normal-case text-gray-400">
                            — bank-confirmed movements
                          </span>
                        </h3>
                        <table className="w-full">
                          <thead>
                            <tr className="text-left">
                              <th className="pb-2 text-[10px] font-medium uppercase tracking-wider text-gray-400">Type</th>
                              <th className="pb-2 text-[10px] font-medium uppercase tracking-wider text-gray-400">Date</th>
                              <th className="pb-2 text-[10px] font-medium uppercase tracking-wider text-gray-400">Counterparty</th>
                              <th className="pb-2 text-right text-[10px] font-medium uppercase tracking-wider text-gray-400">Amount</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detail.cleared_entries.map(e => <EntryRow key={e.id} entry={e} />)}
                          </tbody>
                        </table>
                      </section>
                    </>
                  )}

                  {/* Pending entries */}
                  {detail.pending_entries.length > 0 && (
                    <>
                      <div className="border-t border-gray-100" />
                      <section>
                        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                          Pending claims
                          <span className="ml-1.5 font-normal normal-case text-gray-400">
                            — uncleared outbound
                          </span>
                        </h3>
                        <table className="w-full">
                          <thead>
                            <tr className="text-left">
                              <th className="pb-2 text-[10px] font-medium uppercase tracking-wider text-gray-400">Type</th>
                              <th className="pb-2 text-[10px] font-medium uppercase tracking-wider text-gray-400">Expected</th>
                              <th className="pb-2 text-[10px] font-medium uppercase tracking-wider text-gray-400">Counterparty</th>
                              <th className="pb-2 text-right text-[10px] font-medium uppercase tracking-wider text-gray-400">Amount</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detail.pending_entries.map(e => <EntryRow key={e.id} entry={e} />)}
                          </tbody>
                        </table>
                      </section>
                    </>
                  )}

                  {detail.cleared_entries.length === 0 && detail.pending_entries.length === 0 && (
                    <p className="text-sm text-gray-400">No activity for this group.</p>
                  )}
                </>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
