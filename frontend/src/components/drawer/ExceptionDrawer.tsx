import { AnimatePresence, motion } from 'framer-motion';
import { useState } from 'react';
import { useExceptionDetail } from '../../hooks/useExceptionDetail';
import { Money } from '../shared/Money';
import { StatusPill } from '../shared/StatusPill';
import { ActionBar } from './ActionBar';
import { AuditTimeline } from './AuditTimeline';
import { BankEventFacts } from './BankEventFacts';
import { CandidateTable } from './CandidateTable';
import { EngineReasoningPanel } from './EngineReasoningPanel';

interface ExceptionDrawerProps {
  selectedId: string | null;
  onClose: () => void;
  onToast: (msg: string, variant?: 'success' | 'error' | 'info') => void;
}

export function ExceptionDrawer({ selectedId, onClose, onToast }: ExceptionDrawerProps) {
  const { data: detail, isLoading } = useExceptionDetail(selectedId);
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<Set<string>>(new Set());

  function toggleCandidate(id: string) {
    setSelectedCandidateIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <AnimatePresence>
      {selectedId && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            aria-hidden
          />

          {/* Drawer panel */}
          <motion.aside
            key="drawer"
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-[680px] flex-col bg-white shadow-2xl"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 32, stiffness: 320 }}
            role="dialog"
            aria-modal="true"
            aria-label="Exception detail"
          >
            {/* Header */}
            <div className="flex items-start justify-between border-b border-gray-100 px-6 py-4">
              {isLoading || !detail ? (
                <div className="animate-pulse space-y-2">
                  <div className="h-4 w-56 rounded bg-gray-200" />
                  <div className="h-7 w-32 rounded bg-gray-200" />
                </div>
              ) : (
                <div>
                  <p className="text-xs text-gray-500 truncate max-w-sm">
                    {detail.bank_event.descriptor ?? 'No descriptor'}
                  </p>
                  <div className="mt-1 flex items-baseline gap-3">
                    <Money
                      value={detail.bank_event.amount}
                      className={`text-2xl font-semibold ${
                        detail.bank_event.direction === 'credit' ? 'text-emerald-700' : 'text-gray-900'
                      }`}
                    />
                    <StatusPill status={detail.status} />
                  </div>
                </div>
              )}
              <button
                onClick={onClose}
                className="ml-4 shrink-0 rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#0C7785]"
                aria-label="Close detail panel"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
              {isLoading && (
                <div className="animate-pulse space-y-6">
                  {[120, 200, 160].map((h, i) => (
                    <div key={i} className="rounded-lg bg-gray-100" style={{ height: h }} />
                  ))}
                </div>
              )}

              {!isLoading && detail && (
                <>
                  <BankEventFacts detail={detail} />

                  <div className="border-t border-gray-100" />

                  <EngineReasoningPanel detail={detail} />

                  {detail.candidates.length > 0 && (
                    <>
                      <div className="border-t border-gray-100" />
                      <section>
                        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
                          Alternative candidates
                          <span className="ml-1.5 text-gray-400 font-normal normal-case">
                            — select to match or split
                          </span>
                        </h3>
                        <CandidateTable
                          candidates={detail.candidates}
                          selectedIds={selectedCandidateIds}
                          onToggle={toggleCandidate}
                        />
                      </section>
                    </>
                  )}

                  <div className="border-t border-gray-100" />

                  <ActionBar
                    detail={detail}
                    selectedCandidateIds={selectedCandidateIds}
                    onSuccess={msg => onToast(msg, 'success')}
                    onError={msg => onToast(msg, 'error')}
                    onClose={onClose}
                  />

                  <div className="border-t border-gray-100" />

                  <AuditTimeline bankEventId={detail.bank_event_id} />
                </>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
