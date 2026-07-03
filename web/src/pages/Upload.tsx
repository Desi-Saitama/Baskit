import { useState, useCallback } from 'react';
import { UploadCloud } from 'lucide-react';
import Header from '@/components/layout/Header';
import Card from '@/components/layout/Card';
import { parseUpload, saveOrder, type ParsedOrder, type OrderItem } from '@/lib/api';
import { ALL_APPS, CATEGORIES, rupees } from '@/lib/utils';

export default function Upload() {
  const [autoDetect, setAutoDetect] = useState(true);
  const [selectedApp, setSelectedApp] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [parsing, setParsing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [parsed, setParsed] = useState<ParsedOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  // Editable form state
  const [orderDate, setOrderDate] = useState('');
  const [orderId, setOrderId] = useState('');
  const [appName, setAppName] = useState('');
  const [appCategory, setAppCategory] = useState('');
  const [totalAmount, setTotalAmount] = useState(0);
  const [deliveryFee, setDeliveryFee] = useState(0);
  const [discount, setDiscount] = useState(0);
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<OrderItem[]>([]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files);
    setFiles(prev => [...prev, ...dropped]);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(prev => [...prev, ...Array.from(e.target.files!)]);
    }
  };

  const handleParse = async () => {
    if (files.length === 0) return;
    setError(null);
    setSuccess(null);
    setParsing(true);
    try {
      const file = files[0];
      const app = autoDetect ? undefined : (selectedApp || undefined);
      const result = await parseUpload(file, app);
      const p = result.parsed;
      setParsed(p);
      setOrderDate(p.order_date || new Date().toISOString().split('T')[0]);
      setOrderId(p.order_id || '');
      setAppName(p.resolved_app || selectedApp || '');
      setAppCategory(p.resolved_category || 'groceries');
      setTotalAmount(p.total_amount);
      setDeliveryFee(p.delivery_fee);
      setDiscount(p.discount);
      setItems(p.items || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setParsing(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await saveOrder({
        order_date: orderDate,
        app_name: appName,
        app_category: appCategory,
        order_id: orderId,
        total_amount: totalAmount,
        delivery_fee: deliveryFee,
        discount: discount,
        notes: notes,
        items: items,
      });
      setSuccess('Order saved successfully!');
      setParsed(null);
      setFiles([]);
      setItems([]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const updateItem = (idx: number, field: keyof OrderItem, value: string | number) => {
    setItems(prev => prev.map((it, i) => i === idx ? { ...it, [field]: value } : it));
  };

  const removeItem = (idx: number) => {
    setItems(prev => prev.filter((_, i) => i !== idx));
  };

  const addItem = () => {
    setItems(prev => [...prev, { name: '', brand: '', category: 'Other', quantity: '', unit_price: 0, total_price: 0 }]);
  };

  return (
    <>
      <Header
        title="Upload & parse view"
        subtitle="Drop screenshots or PDFs, review Gemini Vision extraction, then save verified orders."
      />

      {error && (
        <div className="mb-4 rounded-2xl bg-red-500/10 border border-red-500/20 p-4 text-sm text-red-700 animate-fade-in">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-2xl bg-green-500/10 border border-green-500/20 p-4 text-sm text-green-700 animate-fade-in">
          {success}
        </div>
      )}

      <section className="grid gap-4 xl:grid-cols-3">
        {/* App configuration */}
        <Card className="animate-fade-in">
          <b className="text-stone-900">App configuration</b>
          <label className="mt-4 flex items-center gap-3 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={autoDetect}
              onChange={e => setAutoDetect(e.target.checked)}
              className="accent-orange-600"
            />
            Auto-detect app from invoice
          </label>
          {!autoDetect && (
            <div className="mt-4 grid grid-cols-2 gap-2">
              {ALL_APPS.map(a => (
                <button
                  key={a.name}
                  onClick={() => setSelectedApp(a.name)}
                  className={`rounded-xl border px-3 py-2 text-sm transition ${
                    selectedApp === a.name
                      ? 'border-orange-500 bg-orange-500/10 text-orange-900 font-semibold'
                      : 'border-amber-900/10 hover:bg-white/60 text-stone-700'
                  }`}
                >
                  {a.name}
                </button>
              ))}
            </div>
          )}
        </Card>

        {/* File dropzone */}
        <Card className="xl:col-span-2 animate-fade-in delay-1">
          <div
            className={`grid min-h-64 place-items-center rounded-3xl border border-dashed text-center transition-all ${
              dragOver
                ? 'border-orange-500 bg-orange-500/20'
                : 'border-orange-300/70 bg-orange-600/10'
            }`}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <div>
              <UploadCloud className="mx-auto mb-3 text-orange-700" size={44} />
              <b className="text-stone-900">Drop JPG, PNG or PDF invoices</b>
              <p className="text-sm text-stone-500">Multiple files supported · duplicate checks enabled</p>
              <label className="mt-4 inline-block cursor-pointer rounded-xl bg-white/60 px-4 py-2 text-sm text-stone-700 hover:bg-white/80 transition">
                Browse files
                <input type="file" multiple accept="image/*,.pdf" className="hidden" onChange={handleFileSelect} />
              </label>
            </div>
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div className="mt-4 space-y-2">
              {files.map((f, i) => (
                <div key={i} className="flex items-center justify-between rounded-xl bg-white/55 px-3 py-2 text-sm">
                  <span className="truncate">{f.name}</span>
                  <button
                    onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))}
                    className="text-red-400 hover:text-red-600 text-xs"
                  >
                    Remove
                  </button>
                </div>
              ))}
              <button
                onClick={handleParse}
                disabled={parsing}
                className="mt-2 rounded-xl bg-orange-600 px-5 py-2.5 text-sm text-white font-semibold shadow-lg shadow-orange-300/40 hover:bg-orange-700 transition disabled:opacity-50"
              >
                {parsing ? '⏳ Parsing with Gemini...' : '🔍 Parse Invoice'}
              </button>
            </div>
          )}
        </Card>
      </section>

      {/* Review & edit parsed order */}
      {parsed && (
        <Card className="mt-4 animate-fade-in">
          <b className="text-stone-900">Review & edit parsed order</b>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <input value={orderDate} onChange={e => setOrderDate(e.target.value)} placeholder="Order Date" type="date"
              className="rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-2 outline-none focus:ring-2 focus:ring-orange-300" />
            <input value={orderId} onChange={e => setOrderId(e.target.value)} placeholder="Order ID"
              className="rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-2 outline-none focus:ring-2 focus:ring-orange-300" />
            <select value={appName} onChange={e => setAppName(e.target.value)}
              className="rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-2 outline-none focus:ring-2 focus:ring-orange-300">
              <option value="">Select App</option>
              {ALL_APPS.map(a => <option key={a.name} value={a.name}>{a.name}</option>)}
            </select>
            <input value={totalAmount} onChange={e => setTotalAmount(Number(e.target.value))} placeholder="Total Paid" type="number"
              className="rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-2 outline-none focus:ring-2 focus:ring-orange-300" />
            <input value={deliveryFee} onChange={e => setDeliveryFee(Number(e.target.value))} placeholder="Delivery Fee" type="number"
              className="rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-2 outline-none focus:ring-2 focus:ring-orange-300" />
            <input value={discount} onChange={e => setDiscount(Number(e.target.value))} placeholder="Discount" type="number"
              className="rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-2 outline-none focus:ring-2 focus:ring-orange-300" />
            <input value={notes} onChange={e => setNotes(e.target.value)} placeholder="Notes"
              className="rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-2 outline-none focus:ring-2 focus:ring-orange-300 md:col-span-2" />
          </div>

          {/* Line items */}
          <div className="mt-4 overflow-auto">
            <table className="w-full min-w-[700px] text-left text-sm">
              <thead className="font-mono text-xs uppercase tracking-widest text-stone-400">
                <tr>
                  {['Item', 'Brand', 'Category', 'Qty', 'Unit Price', 'Total', ''].map(h => (
                    <th key={h} className="border-b border-amber-900/10 py-2 px-2">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((it, idx) => (
                  <tr key={idx} className="hover:bg-orange-50/60">
                    <td className="py-2 px-1">
                      <input value={it.name} onChange={e => updateItem(idx, 'name', e.target.value)}
                        className="w-full rounded-lg border border-amber-900/10 bg-white/60 px-2 py-1 text-sm outline-none" />
                    </td>
                    <td className="px-1">
                      <input value={it.brand} onChange={e => updateItem(idx, 'brand', e.target.value)}
                        className="w-full rounded-lg border border-amber-900/10 bg-white/60 px-2 py-1 text-sm outline-none" />
                    </td>
                    <td className="px-1">
                      <select value={it.category} onChange={e => updateItem(idx, 'category', e.target.value)}
                        className="w-full rounded-lg border border-amber-900/10 bg-white/60 px-2 py-1 text-sm outline-none">
                        {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </td>
                    <td className="px-1">
                      <input value={it.quantity} onChange={e => updateItem(idx, 'quantity', e.target.value)}
                        className="w-20 rounded-lg border border-amber-900/10 bg-white/60 px-2 py-1 text-sm outline-none" />
                    </td>
                    <td className="px-1">
                      <input value={it.unit_price} onChange={e => updateItem(idx, 'unit_price', Number(e.target.value))} type="number"
                        className="w-20 rounded-lg border border-amber-900/10 bg-white/60 px-2 py-1 text-sm outline-none" />
                    </td>
                    <td className="px-1">
                      <input value={it.total_price} onChange={e => updateItem(idx, 'total_price', Number(e.target.value))} type="number"
                        className="w-20 rounded-lg border border-amber-900/10 bg-white/60 px-2 py-1 text-sm outline-none" />
                    </td>
                    <td className="px-1">
                      <button onClick={() => removeItem(idx)} className="text-red-400 hover:text-red-600 text-xs">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex gap-3">
            <button onClick={addItem}
              className="rounded-xl bg-white/60 px-4 py-2 text-sm text-stone-700 hover:bg-white/80 transition">
              + Add Item
            </button>
            <button onClick={handleSave} disabled={saving}
              className="rounded-2xl bg-[var(--primary)] px-5 py-3 text-[var(--primary-foreground)] font-semibold shadow-lg shadow-orange-300/40 hover:opacity-90 transition disabled:opacity-50">
              {saving ? 'Saving...' : 'Save Order'}
            </button>
          </div>
        </Card>
      )}
    </>
  );
}
