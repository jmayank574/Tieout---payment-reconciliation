import type { StaleAlert } from '../../hooks/useStaleAlerts';

interface Props {
  alert: StaleAlert;
}

function fmt(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
}

export function AlertBanner({ alert }: Props) {
  if (alert.count === 0) return null;

  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
      <svg
        className="mt-0.5 h-4 w-4 shrink-0 text-amber-500"
        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round"
          d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
      </svg>
      <p className="text-sm text-amber-800">
        <span className="font-semibold">
          {alert.count} {alert.count === 1 ? 'exception' : 'exceptions'}
        </span>
        {' '}over{' '}
        <span className="font-medium">{fmt(alert.amountThreshold)}</span>
        {' '}open more than{' '}
        <span className="font-medium">{alert.ageDays} days</span>
        {' '}— needs attention.
      </p>
    </div>
  );
}
