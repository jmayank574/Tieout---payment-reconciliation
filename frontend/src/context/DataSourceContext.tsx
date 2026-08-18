import { createContext, useContext, useEffect, useState } from 'react';

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

// Render's free tier spins backends down when idle; a cold start can take
// up to ~50s to respond. Past this threshold we surface a "waking up" hint
// instead of leaving the viewer staring at a blank skeleton.
const SLOW_HEALTH_CHECK_MS = 4000;

interface DataSourceCtx {
  isLive: boolean;
  checked: boolean;
  waking: boolean;
}

const DataSourceContext = createContext<DataSourceCtx>({ isLive: true, checked: false, waking: false });

export function DataSourceProvider({ children }: { children: React.ReactNode }) {
  const [isLive, setIsLive] = useState(true);
  const [checked, setChecked] = useState(false);
  const [waking, setWaking] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    const slowTimer = setTimeout(() => setWaking(true), SLOW_HEALTH_CHECK_MS);

    fetch(`${BASE_URL}/health`, { signal: ctrl.signal })
      .then(r => {
        setIsLive(r.ok);
        setChecked(true);
      })
      .catch(err => {
        // AbortError means StrictMode cleanup ran — ignore, the re-mount will retry
        if ((err as Error).name !== 'AbortError') {
          setIsLive(false);
          setChecked(true);
        }
      })
      .finally(() => clearTimeout(slowTimer));

    return () => {
      ctrl.abort();
      clearTimeout(slowTimer);
    };
  }, []);

  return (
    <DataSourceContext.Provider value={{ isLive, checked, waking: waking && !checked }}>
      {children}
    </DataSourceContext.Provider>
  );
}

export function useDataSource() {
  return useContext(DataSourceContext);
}
