import { Link2 } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useDataSource } from '../../context/DataSourceContext';

const NAV_ITEMS = [
  { to: '/', label: 'Queue', end: true },
  { to: '/cash-position', label: 'Cash position', end: false },
];

export function TopBar() {
  const { isLive, checked } = useDataSource();

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-gray-200">
      {/* Spectrum accent line */}
      <div className="h-[2px] w-full accent-line" />

      <div className="mx-auto flex min-h-14 max-w-screen-xl flex-wrap items-center justify-between gap-y-2 px-4 py-2 sm:px-6">
        {/* Logo */}
        <div className="flex items-center gap-4 sm:gap-6">
          <span className="flex items-center gap-1.5 text-base font-semibold tracking-tight text-gray-900 select-none">
            <Link2 className="h-4 w-4 text-accent" strokeWidth={2.5} />
            Tieout
          </span>

          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-accent-light text-accent'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Data source badge */}
        {checked && (
          <div
            className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
              isLive
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-amber-50 text-amber-700'
            }`}
          >
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                isLive ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
            />
            {isLive ? 'Live' : 'Demo data'}
          </div>
        )}
      </div>
    </header>
  );
}
