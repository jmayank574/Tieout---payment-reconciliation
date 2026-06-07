import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { GroupPosition } from '../api/types';
import { CashGroupDrawer } from '../components/cash/CashGroupDrawer';
import { CashStatStrip } from '../components/cash/CashStatStrip';
import { CoverageStatusPill } from '../components/cash/CoverageStatusPill';
import { Money } from '../components/shared/Money';
import { useCashPosition } from '../hooks/useCashPosition';

type SortKey = 'coverage' | 'funded' | 'pending' | 'name';
type SortDir = 'asc' | 'desc';

const COVERAGE_ORDER = { shortfall: 0, watch: 1, healthy: 2 };

function sortGroups(groups: GroupPosition[], key: SortKey, dir: SortDir): GroupPosition[] {
  const sorted = [...groups].sort((a, b) => {
    let cmp = 0;
    if (key === 'coverage') {
      cmp = COVERAGE_ORDER[a.coverage_status] - COVERAGE_ORDER[b.coverage_status];
      if (cmp === 0) cmp = parseFloat(a.funded_balance) - parseFloat(b.funded_balance);
    } else if (key === 'funded') {
      cmp = parseFloat(a.funded_balance) - parseFloat(b.funded_balance);
    } else if (key === 'pending') {
      cmp = parseFloat(a.pending_claims_liability) - parseFloat(b.pending_claims_liability);
    } else {
      cmp = a.group_name.localeCompare(b.group_name);
    }
    return dir === 'asc' ? cmp : -cmp;
  });
  return sorted;
}

function SortHeader({
  label,
  sortKey,
  current,
  dir,
  align,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  dir: SortDir;
  align?: 'right';
  onSort: (k: SortKey) => void;
}) {
  const active = current === sortKey;
  return (
    <th
      className={`pb-2 text-[10px] font-medium uppercase tracking-wider text-gray-400 cursor-pointer select-none hover:text-gray-600 transition-colors ${align === 'right' ? 'text-right' : ''}`}
      onClick={() => onSort(sortKey)}
    >
      {label}
      {active && (
        <span className="ml-1 text-[#0C7785]">{dir === 'asc' ? '↑' : '↓'}</span>
      )}
    </th>
  );
}

export function CashPositionPage() {
  const { data, isLoading } = useCashPosition();
  const navigate = useNavigate();
  const [sortKey, setSortKey] = useState<SortKey>('coverage');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);
  const [selectedGroupName, setSelectedGroupName] = useState<string>();

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  function openGroup(group: GroupPosition) {
    setSelectedGroupId(group.group_id);
    setSelectedGroupName(group.group_name);
  }

  function drillToQueue(group: GroupPosition, e: React.MouseEvent) {
    e.stopPropagation();
    navigate(`/?group_id=${group.group_id}&group_name=${encodeURIComponent(group.group_name)}`);
  }

  const groups = data ? sortGroups(data.groups, sortKey, sortDir) : [];

  return (
    <div className="space-y-6">
      {/* Stat strip */}
      <CashStatStrip data={data} isLoading={isLoading} />

      {/* Table */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Employer group positions</h2>
            <p className="mt-0.5 text-xs text-gray-400">
              Funded balance = bank-confirmed credits minus debits. Pending = uncleared claim_payment entries.
            </p>
          </div>
          {!isLoading && data && (
            <span className="text-xs text-gray-400">{data.groups.length} groups</span>
          )}
        </div>

        {isLoading ? (
          <div className="animate-pulse divide-y divide-gray-50">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-5 py-3">
                <div className="h-3 w-40 rounded bg-gray-100" />
                <div className="h-3 w-24 rounded bg-gray-100 ml-auto" />
                <div className="h-3 w-20 rounded bg-gray-100" />
                <div className="h-5 w-16 rounded-full bg-gray-100" />
              </div>
            ))}
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 px-5">
                <th className="px-5 py-2 text-left">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-gray-400 cursor-pointer select-none hover:text-gray-600" onClick={() => handleSort('name')}>
                    Group {sortKey === 'name' && <span className="text-[#0C7785]">{sortDir === 'asc' ? '↑' : '↓'}</span>}
                  </span>
                </th>
                <th className="px-3 py-2 text-right">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-gray-400 cursor-pointer select-none hover:text-gray-600" onClick={() => handleSort('funded')}>
                    Funded balance {sortKey === 'funded' && <span className="text-[#0C7785]">{sortDir === 'asc' ? '↑' : '↓'}</span>}
                  </span>
                </th>
                <th className="px-3 py-2 text-right">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-gray-400 cursor-pointer select-none hover:text-gray-600" onClick={() => handleSort('pending')}>
                    Pending liability {sortKey === 'pending' && <span className="text-[#0C7785]">{sortDir === 'asc' ? '↑' : '↓'}</span>}
                  </span>
                </th>
                <th className="px-3 py-2 text-right">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-gray-400">
                    Available
                  </span>
                </th>
                <th className="px-3 py-2 text-center">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-gray-400 cursor-pointer select-none hover:text-gray-600" onClick={() => handleSort('coverage')}>
                    Status {sortKey === 'coverage' && <span className="text-[#0C7785]">{sortDir === 'asc' ? '↑' : '↓'}</span>}
                  </span>
                </th>
                <th className="px-3 py-2 text-right">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-gray-400">Members</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {groups.map(group => (
                <tr
                  key={group.group_id}
                  className="hover:bg-[#F0FAFB] cursor-pointer transition-colors"
                  onClick={() => openGroup(group)}
                >
                  <td className="px-5 py-3 text-sm font-medium text-gray-900">{group.group_name}</td>
                  <td className="px-3 py-3 text-right">
                    <Money
                      value={group.funded_balance}
                      showSign={true}
                      className={`text-sm ${parseFloat(group.funded_balance) < 0 ? 'text-red-700' : 'text-gray-900'}`}
                    />
                  </td>
                  <td className="px-3 py-3 text-right">
                    <Money
                      value={group.pending_claims_liability}
                      className={`text-sm ${parseFloat(group.pending_claims_liability) > 0 ? 'text-amber-700' : 'text-gray-400'}`}
                    />
                  </td>
                  <td className="px-3 py-3 text-right">
                    <Money
                      value={group.available_to_cover}
                      showSign={true}
                      className={`text-sm ${parseFloat(group.available_to_cover) < 0 ? 'text-red-700' : 'text-gray-900'}`}
                    />
                  </td>
                  <td className="px-3 py-3 text-center">
                    <CoverageStatusPill status={group.coverage_status} />
                  </td>
                  <td className="px-3 py-3 text-right text-sm tabular-nums text-gray-500">
                    {group.member_count.toLocaleString()}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <button
                      onClick={e => drillToQueue(group, e)}
                      className="text-xs font-medium text-[#0C7785] hover:underline whitespace-nowrap"
                      title={`View ${group.group_name}'s exceptions in the queue`}
                    >
                      View exceptions →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <CashGroupDrawer
        groupId={selectedGroupId}
        groupName={selectedGroupName}
        onClose={() => setSelectedGroupId(null)}
      />
    </div>
  );
}
