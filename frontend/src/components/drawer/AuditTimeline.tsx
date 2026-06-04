import { useAudit } from '../../hooks/useAudit';
import type { AuditEvent } from '../../api/types';

const ACTION_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  accept:    { label: 'Accepted',      color: 'text-emerald-700', bg: 'bg-emerald-100' },
  match:     { label: 'Matched',       color: 'text-[#0C7785]',   bg: 'bg-[#E0F4F6]' },
  split:     { label: 'Split',         color: 'text-sky-700',     bg: 'bg-sky-100' },
  write_off: { label: 'Written off',   color: 'text-red-700',     bg: 'bg-red-100' },
  flag:      { label: 'Flagged',       color: 'text-amber-700',   bg: 'bg-amber-100' },
  reopen:    { label: 'Reopened',      color: 'text-gray-700',    bg: 'bg-gray-100' },
};

function formatTs(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function AuditEntry({ event }: { event: AuditEvent }) {
  const cfg = ACTION_CONFIG[event.action] ?? { label: event.action, color: 'text-gray-700', bg: 'bg-gray-100' };
  const before = event.payload.before;
  const after = event.payload.after;

  return (
    <div className="relative flex gap-3 pb-5 last:pb-0">
      {/* Vertical line */}
      <div className="absolute left-[11px] top-5 bottom-0 w-px bg-gray-100" aria-hidden />

      {/* Dot */}
      <div className={`relative z-10 mt-0.5 flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-[9px] font-bold ${cfg.bg} ${cfg.color}`}>
        {event.action[0].toUpperCase()}
      </div>

      <div className="flex-1 min-w-0 pt-0.5">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className={`text-xs font-semibold ${cfg.color}`}>{cfg.label}</span>
          <span className="text-[11px] text-gray-400">by {event.actor}</span>
          <span
            className="text-[11px] text-gray-400 ml-auto"
            style={{ fontFamily: '"JetBrains Mono", monospace' }}
          >
            {formatTs(event.created_at)}
          </span>
        </div>

        {/* Before → after state */}
        {before.status != null && after.status != null && (
          <p className="mt-0.5 text-[11px] text-gray-500">
            {String(before.status).replace(/_/g, ' ')}
            <span className="mx-1 text-gray-300">→</span>
            {String(after.status).replace(/_/g, ' ')}
          </p>
        )}

        {/* Note */}
        {event.payload.note && (
          <p className="mt-1 rounded bg-gray-50 px-2 py-1 text-[11px] text-gray-600 italic">
            "{event.payload.note}"
          </p>
        )}
      </div>
    </div>
  );
}

interface AuditTimelineProps {
  bankEventId: string;
}

export function AuditTimeline({ bankEventId }: AuditTimelineProps) {
  const { data: events, isLoading } = useAudit(bankEventId);

  return (
    <section>
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
        Audit history
      </h3>

      {isLoading && (
        <div className="space-y-3 animate-pulse">
          {[1, 2].map(i => (
            <div key={i} className="flex gap-3">
              <div className="h-5 w-5 rounded-full bg-gray-200 shrink-0" />
              <div className="flex-1 space-y-1.5">
                <div className="h-3 w-32 rounded bg-gray-200" />
                <div className="h-2.5 w-48 rounded bg-gray-100" />
              </div>
            </div>
          ))}
        </div>
      )}

      {!isLoading && events?.length === 0 && (
        <p className="text-sm text-gray-400">No actions recorded yet.</p>
      )}

      {!isLoading && events && events.length > 0 && (
        <div>
          {events.map(e => (
            <AuditEntry key={e.id} event={e} />
          ))}
        </div>
      )}
    </section>
  );
}
