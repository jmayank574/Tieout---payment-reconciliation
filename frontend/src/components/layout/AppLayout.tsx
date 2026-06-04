import { Outlet } from 'react-router-dom';
import { TopBar } from './TopBar';

export function AppLayout() {
  return (
    <div className="min-h-screen bg-[#F7F8F9]">
      <TopBar />
      <main className="mx-auto max-w-screen-xl px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
