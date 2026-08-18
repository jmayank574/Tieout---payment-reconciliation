import { Outlet } from 'react-router-dom';
import { ColdStartBanner } from './ColdStartBanner';
import { TopBar } from './TopBar';

export function AppLayout() {
  return (
    <div className="min-h-screen bg-canvas">
      <TopBar />
      <main className="mx-auto max-w-screen-xl px-4 py-6 sm:px-6">
        <ColdStartBanner />
        <Outlet />
      </main>
    </div>
  );
}
