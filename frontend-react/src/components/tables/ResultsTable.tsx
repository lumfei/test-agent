import { useState, useMemo } from 'react';
import type { TestResult } from '../../types';
import { StatusBadge } from '../common/StatusBadge';
import { CATEGORY_LABELS, METHOD_COLORS } from '../../utils/constants';

interface ResultsTableProps {
  results: TestResult[];
  categories?: string[];
  selectedCategories?: string[];
  onCategoryChange?: (cats: string[]) => void;
  resultFilter?: 'all' | 'passed' | 'failed';
  onResultFilterChange?: (f: 'all' | 'passed' | 'failed') => void;
  pageSize?: number;
}

export function ResultsTable({
  results,
  categories,
  selectedCategories = [],
  onCategoryChange,
  resultFilter = 'all',
  onResultFilterChange,
  pageSize = 25,
}: ResultsTableProps) {
  const [sortKey, setSortKey] = useState<keyof TestResult>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [page, setPage] = useState(0);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const filtered = useMemo(() => {
    let r = results;
    if (selectedCategories.length > 0) {
      r = r.filter((item) => selectedCategories.includes(item.category));
    }
    if (resultFilter === 'passed') r = r.filter((item) => item.passed);
    if (resultFilter === 'failed') r = r.filter((item) => !item.passed);
    return r;
  }, [results, selectedCategories, resultFilter]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  const paged = useMemo(() => {
    const start = page * pageSize;
    return sorted.slice(start, start + pageSize);
  }, [sorted, page, pageSize]);

  const totalPages = Math.ceil(sorted.length / pageSize);

  const handleSort = (key: keyof TestResult) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
    setPage(0);
  };

  if (results.length === 0) {
    return <p className="text-sm text-gray-400 text-center py-8">暂无数据</p>;
  }

  return (
    <div className="bg-white rounded-lg border border-gray-100 overflow-hidden">
      {/* Filters */}
      {(categories || onResultFilterChange) && (
        <div className="px-4 py-2 border-b border-gray-100 flex items-center gap-3 bg-gray-50">
          {categories && onCategoryChange && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">类别:</span>
              <div className="flex flex-wrap gap-1">
                {categories.map((cat) => {
                  const active = selectedCategories.includes(cat);
                  return (
                    <button
                      key={cat}
                      onClick={() => {
                        const next = active
                          ? selectedCategories.filter((c) => c !== cat)
                          : [...selectedCategories, cat];
                        onCategoryChange(next);
                        setPage(0);
                      }}
                      className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                        active
                          ? 'bg-indigo-100 text-indigo-700 border-indigo-300'
                          : 'bg-white text-gray-500 border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      {CATEGORY_LABELS[cat] || cat}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          {onResultFilterChange && (
            <div className="flex items-center gap-1 ml-auto">
              {(['all', 'passed', 'failed'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => { onResultFilterChange(f); setPage(0); }}
                  className={`px-2 py-0.5 text-xs rounded ${
                    resultFilter === f
                      ? 'bg-gray-700 text-white'
                      : 'bg-white text-gray-500 border border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {f === 'all' ? '全部' : f === 'passed' ? '通过' : '失败'}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Count */}
      <div className="px-4 py-2 border-b border-gray-100 bg-white">
        <span className="text-xs text-gray-400">共 {filtered.length} 条结果</span>
        {selectedCategories.length > 0 && (
          <span className="text-xs text-indigo-500 ml-2">(已筛选)</span>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              <Th label="#" />
              <Th label="用例名称" sortKey="name" currentSort={sortKey} sortDir={sortDir} onSort={handleSort} />
              <Th label="方法" sortKey="method" currentSort={sortKey} sortDir={sortDir} onSort={handleSort} />
              <Th label="路径" sortKey="path" currentSort={sortKey} sortDir={sortDir} onSort={handleSort} />
              <Th label="状态码" sortKey="status_code" currentSort={sortKey} sortDir={sortDir} onSort={handleSort} />
              <Th label="耗时" sortKey="elapsed_ms" currentSort={sortKey} sortDir={sortDir} onSort={handleSort} />
              <Th label="类别" sortKey="category" currentSort={sortKey} sortDir={sortDir} onSort={handleSort} />
              <Th label="结果" sortKey="passed" currentSort={sortKey} sortDir={sortDir} onSort={handleSort} />
            </tr>
          </thead>
          <tbody>
            {paged.map((r, i) => {
              const absIdx = page * pageSize + i;
              const methodColor = METHOD_COLORS[r.method] || 'bg-gray-100 text-gray-600';
              return (
                <>
                  <tr
                    key={absIdx}
                    onClick={() => setExpandedIdx(expandedIdx === absIdx ? null : absIdx)}
                    className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-3 py-2 text-xs text-gray-400">{absIdx + 1}</td>
                    <td className="px-3 py-2 text-xs truncate max-w-48">{r.name}</td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex px-1.5 py-0.5 text-xs font-medium rounded ${methodColor}`}>
                        {r.method}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-600 truncate max-w-64 font-mono">{r.path}</td>
                    <td className="px-3 py-2 text-xs font-mono text-center">{r.status_code || '-'}</td>
                    <td className="px-3 py-2 text-xs text-gray-500 text-right">{r.elapsed_ms > 0 ? `${Math.round(r.elapsed_ms)}ms` : '-'}</td>
                    <td className="px-3 py-2 text-xs text-gray-500">{CATEGORY_LABELS[r.category] || r.category}</td>
                    <td className="px-3 py-2">
                      <StatusBadge passed={r.passed} error={!!r.error} />
                    </td>
                  </tr>
                  {/* Expanded row with check details */}
                  {expandedIdx === absIdx && (
                    <tr>
                      <td colSpan={8} className="bg-gray-50 px-6 py-3 border-b border-gray-100">
                        <div className="space-y-2">
                          {r.error && (
                            <div className="bg-red-50 border border-red-100 rounded p-2">
                              <span className="text-xs font-medium text-red-700">错误: </span>
                              <span className="text-xs text-red-600">{r.error}</span>
                            </div>
                          )}
                          {r.checks.length > 0 && (
                            <div>
                              <p className="text-xs font-medium text-gray-500 mb-1">验证项:</p>
                              {r.checks.map((c, ci) => (
                                <div key={ci} className="flex items-center gap-2 text-xs py-0.5">
                                  <span className={c.passed ? 'text-green-500' : 'text-red-500'}>
                                    {c.passed ? '✓' : '✗'}
                                  </span>
                                  <span className="text-gray-600">{c.check_name}</span>
                                  {!c.passed && <span className="text-gray-400">— {c.detail}</span>}
                                </div>
                              ))}
                            </div>
                          )}
                          {r.response_preview && (
                            <div>
                              <p className="text-xs font-medium text-gray-500 mb-1">响应预览:</p>
                              <pre className="text-xs text-gray-600 bg-gray-100 rounded p-2 overflow-x-auto max-h-32">
                                {r.response_preview.slice(0, 500)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-4 py-2 border-t border-gray-100 flex items-center justify-between bg-gray-50">
          <span className="text-xs text-gray-400">
            第 {page + 1} / {totalPages} 页
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-2 py-1 text-xs border border-gray-200 rounded bg-white disabled:opacity-30 hover:bg-gray-50"
            >
              上一页
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="px-2 py-1 text-xs border border-gray-200 rounded bg-white disabled:opacity-30 hover:bg-gray-50"
            >
              下一页
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Header cell with optional sorting
function Th({
  label,
  sortKey,
  currentSort,
  sortDir,
  onSort,
}: {
  label: string;
  sortKey?: keyof TestResult;
  currentSort?: keyof TestResult;
  sortDir?: 'asc' | 'desc';
  onSort?: (key: keyof TestResult) => void;
}) {
  const isSorted = sortKey && currentSort === sortKey;

  return (
    <th
      onClick={() => sortKey && onSort?.(sortKey)}
      className={`px-3 py-2 text-xs font-medium text-gray-500 text-left ${
        sortKey ? 'cursor-pointer hover:text-gray-700 select-none' : ''
      }`}
    >
      {label}
      {isSorted && <span className="ml-1">{sortDir === 'asc' ? '▲' : '▼'}</span>}
    </th>
  );
}
