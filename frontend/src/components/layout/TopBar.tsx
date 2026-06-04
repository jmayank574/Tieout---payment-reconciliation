import { NavLink } from 'react-router-dom';
import { useDataSource } from '../../context/DataSourceContext';

export function TopBar() {
  const { isLive, checked } = useDataSource();

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-gray-200">
      {/* Spectrum accent line */}
      <div className="h-[2px] w-full accent-line" />

      <div className="mx-auto flex h-14 max-w-screen-xl items-center justify-between px-6">
        {/* Logo */}
        <div className="flex items-center gap-6">
          <span className="text-base font-semibold tracking-tight text-gray-900 select-none">
            Tieout
          </span>

          <nav className="flex items-center gap-1">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-[#F0FAFB] text-[#0C7785]'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              Queue
            </NavLink>
            <NavLink
              to="/scorecard"
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-[#F0FAFB] text-[#0C7785]'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              Scorecard
            </NavLink>
            <NavLink
              to="/cash-position"
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-[#F0FAFB] text-[#0C7785]'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              Cash position
            </NavLink>
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
