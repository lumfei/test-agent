interface LoadingSkeletonProps {
  rows?: number;
  type?: 'card' | 'table' | 'chart';
}

export function LoadingSkeleton({ rows = 5, type = 'table' }: LoadingSkeletonProps) {
  if (type === 'card') {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="bg-white rounded-lg p-4 border border-gray-100 animate-pulse">
            <div className="h-3 bg-gray-200 rounded w-12 mb-3" />
            <div className="h-7 bg-gray-200 rounded w-16" />
          </div>
        ))}
      </div>
    );
  }

  if (type === 'chart') {
    return (
      <div className="bg-white rounded-lg p-6 border border-gray-100 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-32 mb-4" />
        <div className="h-64 bg-gray-100 rounded" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-100 animate-pulse">
      <div className="px-4 py-3 border-b border-gray-100">
        <div className="h-4 bg-gray-200 rounded w-24" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="px-4 py-3 border-b border-gray-50 flex gap-4">
          <div className="h-4 bg-gray-100 rounded flex-1" />
          <div className="h-4 bg-gray-100 rounded w-16" />
          <div className="h-4 bg-gray-100 rounded w-20" />
        </div>
      ))}
    </div>
  );
}
