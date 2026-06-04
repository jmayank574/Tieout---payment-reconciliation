import { createContext, useContext, useEffect, useState } from 'react';

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000';

interface DataSourceCtx {
  isLive: boolean;
  checked: boolean;
}

const DataSourceContext = createContext<DataSourceCtx>({ isLive: true, checked: false });

export function DataSourceProvider({ children }: { children: React.ReactNode }) {
  const [isLive, setIsLive] = useState(true);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();

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
      });

    return () => ctrl.abort();
  }, []);

  return (
    <DataSourceContext.Provider value={{ isLive, checked }}>
      {children}
    </DataSourceContext.Provider>
  );
}

export function useDataSource() {
  return useContext(DataSourceContext);
}
