import { useState } from 'react';
import Header from '@/components/layout/Header';
import Card from '@/components/layout/Card';

export default function BulkImport() {
  const [dir, setDir] = useState('/home/me/receipts/quick-commerce');
  const [recursive, setRecursive] = useState(true);
  const [autoSave, setAutoSave] = useState(false);
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState<{ text: string; type: 'success' | 'skip' | 'error' | 'info' }[]>([
    { text: 'Ready to scan. Configure source and click Start.', type: 'info' },
  ]);

  const handleStart = () => {
    setRunning(true);
    setLogs(prev => [...prev, { text: '⏳ Starting bulk scan...', type: 'info' }]);
    // Note: This would call a WebSocket/SSE endpoint in production
    setTimeout(() => {
      setLogs(prev => [
        ...prev,
        { text: '✅ Parsed invoice_1.pdf', type: 'success' },
        { text: '⏭️ Skipped duplicate order_102', type: 'skip' },
        { text: '❌ Failed invoice_3.jpg — rate limit, trying key 03', type: 'error' },
        { text: '⏳ 28 pending · 114 done', type: 'info' },
      ]);
      setRunning(false);
    }, 2000);
  };

  return (
    <>
      <Header
        title="Bulk import console"
        subtitle="Scan local invoice folders, resume safely, rotate API keys and review parsed queue."
      />

      <section className="grid gap-4 xl:grid-cols-3">
        <Card className="animate-fade-in">
          <b className="text-stone-900">Source configuration</b>
          <input
            value={dir}
            onChange={e => setDir(e.target.value)}
            className="mt-4 w-full rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-3 text-sm outline-none focus:ring-2 focus:ring-orange-300"
            placeholder="/path/to/invoices"
          />
          <div className="mt-4 space-y-2 text-sm">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={recursive} onChange={e => setRecursive(e.target.checked)} className="accent-orange-600" />
              Recursive directories
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={autoSave} onChange={e => setAutoSave(e.target.checked)} className="accent-orange-600" />
              Auto-save parsed orders
            </label>
          </div>
          <div className="mt-5 flex gap-2">
            <button
              onClick={handleStart}
              disabled={running}
              className="rounded-xl bg-green-500 px-4 py-2 text-sm text-black font-semibold hover:bg-green-600 transition disabled:opacity-50"
            >
              {running ? '⏳ Running...' : '▶ Start'}
            </button>
            {running && (
              <button
                onClick={() => setRunning(false)}
                className="rounded-xl bg-red-500/20 px-4 py-2 text-sm text-red-700 hover:bg-red-500/30 transition"
              >
                Cancel
              </button>
            )}
          </div>
        </Card>

        {/* Terminal log */}
        <Card className="xl:col-span-2 bg-stone-900 animate-fade-in delay-1">
          <div className="font-mono text-sm max-h-80 overflow-y-auto space-y-1">
            {logs.map((log, i) => (
              <p key={i} className={
                log.type === 'success' ? 'text-green-300' :
                log.type === 'skip' ? 'text-stone-300' :
                log.type === 'error' ? 'text-red-300' :
                'text-amber-300'
              }>
                {log.text}
              </p>
            ))}
            {running && (
              <p className="text-amber-300 animate-pulse">Processing...</p>
            )}
          </div>
        </Card>
      </section>
    </>
  );
}
