import { AlertTriangle } from 'lucide-react';
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
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
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
