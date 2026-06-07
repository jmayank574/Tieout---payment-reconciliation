import React from 'react';

export function SkeletonRow() {
  return (
    <tr className="animate-pulse">
      <td className="px-4 py-3">
        <div className="h-3.5 w-48 rounded bg-gray-200" />
        <div className="mt-1.5 h-2.5 w-24 rounded bg-gray-100" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3.5 w-20 rounded bg-gray-200 ml-auto" />
      </td>
      <td className="px-4 py-3">
        <div className="h-5 w-14 rounded bg-gray-200" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3 w-16 rounded bg-gray-200" />
      </td>
      <td className="px-4 py-3">
        <div className="h-3 w-8 rounded bg-gray-200" />
      </td>
      <td className="px-4 py-3">
        <div className="h-5 w-20 rounded bg-gray-200" />
      </td>
    </tr>
  );
}

export function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border border-gray-200 bg-white p-5">
      <div className="h-3 w-24 rounded bg-gray-200" />
      <div className="mt-3 h-7 w-36 rounded bg-gray-200" />
      <div className="mt-2 h-2.5 w-16 rounded bg-gray-100" />
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  description?: string | React.ReactNode;
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <tr>
      <td colSpan={6} className="px-4 py-16 text-center">
        <p className="text-sm font-medium text-gray-900">{title}</p>
        {description && <p className="mt-1 text-sm text-gray-500">{description}</p>}
      </td>
    </tr>
  );
}
