import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/layout/AppLayout';
import { DataSourceProvider } from './context/DataSourceContext';
import { CashPositionPage } from './pages/CashPositionPage';
import { QueuePage } from './pages/QueuePage';
import { ScorecardPage } from './pages/ScorecardPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <DataSourceProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<QueuePage />} />
              <Route path="scorecard" element={<ScorecardPage />} />
              <Route path="cash-position" element={<CashPositionPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </DataSourceProvider>
    </QueryClientProvider>
  );
}
