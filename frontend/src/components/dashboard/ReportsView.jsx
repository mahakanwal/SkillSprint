import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { FileBarChart, Download, Printer, FileSpreadsheet } from 'lucide-react';
import apiClient from '../../api/apiClient';
import { Alert, Button, Card, CardHeader, EmptyState, PageHeader, SearchInput, SkeletonRows, Tabs, errorMessage } from '../ui/primitives';
import { Pagination, usePagination } from '../ui/Pagination';

/* ==========================================================================
   ReportsView — SRS Steps 62-63 / lxi-lxii.
   Report rows come from GET /reports/{name}. Export:
     CSV / Excel  -> GET /reports/{name}?format=csv (UTF-8 BOM, opens in Excel)
     PDF          -> print view of the full report ("Save as PDF")
   ========================================================================== */
const label = (k) => k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
const cell = (v) => (v === null || v === undefined || v === '' ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v));

const printReport = (title, columns, rows) => {
  const w = window.open('', '_blank');
  if (!w) return;
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  w.document.write(`<!doctype html><html><head><title>${esc(title)}</title><style>
    body{font-family:"Hanken Grotesk",system-ui,sans-serif;margin:24px;color:#111}
    h1{font-size:18px;margin:0 0 4px} p{color:#555;font-size:12px;margin:0 0 16px}
    table{border-collapse:collapse;width:100%;font-size:11px} th,td{border:1px solid #ccc;padding:5px 6px;text-align:left;vertical-align:top}
    th{background:#f1f1f1} @page{size:landscape;margin:12mm}
  </style></head><body><h1>SkillSprint AI · ${esc(title)}</h1><p>Generated ${esc(new Date().toLocaleString())} · ${rows.length} rows</p>
  <table><thead><tr>${columns.map((c) => `<th>${esc(label(c))}</th>`).join('')}</tr></thead>
  <tbody>${rows.map((r) => `<tr>${columns.map((c) => `<td>${esc(cell(r[c]))}</td>`).join('')}</tr>`).join('')}</tbody></table>
  <script>window.onload=()=>{window.print()}</script></body></html>`);
  w.document.close();
};

export const ReportsView = () => {
  const [reports, setReports] = useState([]);
  const [active, setActive] = useState('employee-progress');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [query, setQuery] = useState('');

  useEffect(() => {
    apiClient.get('/reports/').then((r) => setReports(r.data)).catch((e) => setError(errorMessage(e, 'Could not load reports.')));
  }, []);

  useEffect(() => {
    setData(null); setError(null); setQuery('');
    apiClient.get(`/reports/${active}`).then((r) => setData(r.data)).catch((e) => setError(errorMessage(e, 'Could not load report.')));
  }, [active]);

  const columns = useMemo(() => (data?.rows?.[0] ? Object.keys(data.rows[0]) : []), [data]);
  const filtered = useMemo(() => {
    if (!data) return [];
    const q = query.toLowerCase();
    return q ? data.rows.filter((r) => Object.values(r).some((v) => cell(v).toLowerCase().includes(q))) : data.rows;
  }, [data, query]);
  const pager = usePagination(filtered, { pageSize: 12, resetKey: `${active}|${query}` });

  const downloadCsv = async () => {
    setDownloading(true);
    try {
      const res = await apiClient.get(`/reports/${active}`, { params: { format: 'csv' }, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'text/csv' }));
      const a = document.createElement('a');
      a.href = url; a.download = `skillsprint_${active}.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(errorMessage(e, 'Export failed.'));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        description="Generated from live data. Export as CSV (opens in Excel) or print to PDF."
        actions={data && (
          <>
            <Button variant="secondary" icon={FileSpreadsheet} loading={downloading} onClick={downloadCsv}>CSV / Excel</Button>
            <Button variant="secondary" icon={Printer} onClick={() => printReport(data.title, columns, filtered)} disabled={!filtered.length}>PDF</Button>
          </>
        )}
      />
      {error && <Alert tone="danger" onDismiss={() => setError(null)}>{error}</Alert>}

      <Tabs layoutId="report-tabs" active={active} onChange={setActive}
        tabs={reports.map((r) => ({ key: r.name, label: r.title }))} />

      <Card padded={false} className="overflow-hidden">
        <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <CardHeader icon={FileBarChart} title={data?.title || 'Report'} description={data ? `${data.count} row(s)` : 'Loading…'} />
          <SearchInput value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search this report" className="w-full sm:w-64" />
        </div>
        {!data && !error && <SkeletonRows rows={6} />}
        {data && data.rows.length === 0 && <EmptyState icon={Download} title="No data for this report yet" description="Generate and validate plans to populate it." />}
        {data && data.rows.length > 0 && (
          <>
            <div className="table-wrap border-t border-line">
              <table className="table">
                <thead><tr>{columns.map((c) => <th key={c}>{label(c)}</th>)}</tr></thead>
                <motion.tbody key={`${active}-${pager.page}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }}>
                  {pager.pageItems.map((r, i) => (
                    <tr key={i} className="align-top">
                      {columns.map((c) => (
                        <td key={c} className="min-w-[120px] max-w-[320px] text-[12.5px]"><span className="line-clamp-3 text-break" title={cell(r[c])}>{cell(r[c])}</span></td>
                      ))}
                    </tr>
                  ))}
                </motion.tbody>
              </table>
            </div>
            <Pagination {...pager} onPageChange={pager.setPage} noun="rows" />
          </>
        )}
      </Card>
    </div>
  );
};

export default ReportsView;
