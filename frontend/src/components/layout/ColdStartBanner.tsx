import { Loader2 } from 'lucide-react';
import { useDataSource } from '../../context/DataSourceContext';

export function ColdStartBanner() {
  const { waking } = useDataSource();

  if (!waking) return null;

  return (
    <div className="mb-6 flex items-center gap-2.5 rounded-lg border border-accent/20 bg-accent-light px-4 py-3 text-sm text-accent animate-fade-in">
      <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
      <p>
        Waking up the server — the demo backend sleeps when idle, first load can take up to a minute.
      </p>
    </div>
  );
}
