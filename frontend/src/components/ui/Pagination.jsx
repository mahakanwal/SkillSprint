import React, { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

/* ==========================================================================
   Client-side pagination.

   None of the existing list endpoints (/documents/list, /roles/,
   /employees/, /requirements/, /review/queue …) are paginated on the
   backend, and the API is intentionally left unchanged. These helpers only
   slice the list that is already in memory, AFTER search/filtering, so
   search and filters keep working exactly as before.

   usePagination(items, { pageSize, resetKey })
     - resetKey: when it changes (e.g. the search text), go back to page 1.
     - if the list shrinks (e.g. a row was deleted), the page is clamped.
   ========================================================================== */
export function usePagination(items, { pageSize = 10, resetKey } = {}) {
  const [page, setPage] = useState(1);
  const total = items.length;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  useEffect(() => { setPage(1); }, [resetKey]);
  useEffect(() => { if (page > pageCount) setPage(pageCount); }, [page, pageCount]);

  const current = Math.min(page, pageCount);
  const startIndex = (current - 1) * pageSize;
  const pageItems = useMemo(() => items.slice(startIndex, startIndex + pageSize), [items, startIndex, pageSize]);

  return {
    page: current,
    setPage,
    pageCount,
    pageSize,
    total,
    pageItems,
    from: total === 0 ? 0 : startIndex + 1,
    to: Math.min(startIndex + pageSize, total),
  };
}

function pageList(current, count) {
  if (count <= 7) return Array.from({ length: count }, (_, i) => i + 1);
  const pages = new Set([1, count, current, current - 1, current + 1]);
  if (current <= 3) [2, 3, 4].forEach((p) => pages.add(p));
  if (current >= count - 2) [count - 1, count - 2, count - 3].forEach((p) => pages.add(p));
  const sorted = [...pages].filter((p) => p >= 1 && p <= count).sort((a, b) => a - b);
  const out = [];
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push(`gap-${p}`);
    out.push(p);
  });
  return out;
}

export const Pagination = ({ page, pageCount, total, from, to, onPageChange, noun = 'results', className = '' }) => {
  if (total === 0) return null;
  const pages = pageList(page, pageCount);
  const btn = 'grid h-8 min-w-8 place-items-center rounded-lg px-2 text-[13px] font-medium tabular-nums transition-colors';

  return (
    <nav
      aria-label="Pagination"
      className={`flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 sm:px-5 ${className}`}
    >
      <p className="text-[12.5px] text-subtle tabular-nums">
        Showing <span className="text-slate-300">{from}–{to}</span> of <span className="text-slate-300">{total}</span> {noun}
      </p>

      {pageCount > 1 && (
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            className={`${btn} gap-1 text-muted hover:bg-white/5 hover:text-fg disabled:pointer-events-none disabled:opacity-40`}
            aria-label="Previous page"
          >
            <span className="flex items-center gap-1"><ChevronLeft size={15} /><span className="hidden sm:inline">Previous</span></span>
          </button>

          <span className="px-2 text-[12.5px] text-muted tabular-nums sm:hidden">
            {page} / {pageCount}
          </span>

          <ul className="hidden items-center gap-1 sm:flex">
            {pages.map((p) =>
              typeof p === 'string' ? (
                <li key={p} className="px-1 text-subtle" aria-hidden="true">…</li>
              ) : (
                <li key={p}>
                  <button
                    type="button"
                    onClick={() => onPageChange(p)}
                    aria-current={p === page ? 'page' : undefined}
                    className={`${btn} ${
                      p === page
                        ? 'border border-line-strong bg-surface-3 text-fg'
                        : 'text-muted hover:bg-white/5 hover:text-fg'
                    }`}
                  >
                    {p}
                  </button>
                </li>
              )
            )}
          </ul>

          <button
            type="button"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= pageCount}
            className={`${btn} text-muted hover:bg-white/5 hover:text-fg disabled:pointer-events-none disabled:opacity-40`}
            aria-label="Next page"
          >
            <span className="flex items-center gap-1"><span className="hidden sm:inline">Next</span><ChevronRight size={15} /></span>
          </button>
        </div>
      )}
    </nav>
  );
};

export default Pagination;
