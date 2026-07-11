import { useCallback, useEffect, useState } from 'react';
import { RefreshCw, Search } from 'lucide-react';
import Header from '@/components/layout/Header';
import Card from '@/components/layout/Card';
import {
  deleteOrder, getOrder, getOrders,
  type Order, type OrderItem,
} from '@/lib/api';
import { formatDate, rupees } from '@/lib/utils';

const PAGE_SIZE = 50;

export default function History() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [submittedSearch, setSubmittedSearch] = useState('');
  const [expanded, setExpanded] = useState<number | null>(null);
  const [items, setItems] = useState<OrderItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getOrders(page * PAGE_SIZE, PAGE_SIZE, undefined, submittedSearch || undefined);
      setOrders(response.orders);
      setTotal(response.total);
    } catch (e: any) {
      setError(e.message || 'Could not load invoice history');
    } finally {
      setLoading(false);
    }
  }, [page, submittedSearch]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  const openOrder = async (id: number) => {
    if (expanded === id) {
      setExpanded(null);
      setItems([]);
      return;
    }
    setExpanded(id);
    setItems([]);
    try {
      const response = await getOrder(id);
      setItems(response.items);
    } catch {
      setItems([]);
    }
  };

  const removeOrder = async (id: number) => {
    if (!confirm('Delete this saved invoice? This cannot be undone.')) return;
    try {
      await deleteOrder(id);
      if (expanded === id) setExpanded(null);
      await loadOrders();
    } catch (e: any) {
      alert(e.message || 'Could not delete this invoice');
    }
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <Header
        title="Invoice history"
        subtitle="Every invoice saved from Baskit on Android or the web appears here."
        actions={
          <button
            onClick={loadOrders}
            disabled={loading}
            className="rounded-full bg-white/60 p-2 text-stone-600 transition hover:bg-white disabled:opacity-50"
            aria-label="Refresh invoice history"
          >
            <RefreshCw size={17} className={loading ? 'animate-spin' : ''} />
          </button>
        }
      />

      <Card>
        <form
          className="flex gap-2"
          onSubmit={event => {
            event.preventDefault();
            setPage(0);
            setSubmittedSearch(search.trim());
          }}
        >
          <label className="flex flex-1 items-center gap-2 rounded-xl bg-white/60 px-3 py-2 text-stone-500">
            <Search size={16} />
            <input
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="Search app, invoice ID, or notes"
              className="w-full bg-transparent text-sm outline-none placeholder:text-stone-400"
            />
          </label>
          <button className="rounded-xl bg-[var(--primary)] px-4 text-sm font-semibold text-[var(--primary-foreground)]">
            Search
          </button>
        </form>
        <p className="mt-3 text-sm text-stone-500">
          {total} saved invoice{total === 1 ? '' : 's'}{submittedSearch ? ` matching “${submittedSearch}”` : ''}
        </p>
      </Card>

      <section className="mt-4 space-y-2">
        {loading && <Card className="h-24 animate-pulse bg-amber-100/50" />}
        {error && <Card className="text-sm text-red-700">{error}</Card>}
        {!loading && !error && orders.map(order => (
          <Card key={order.id} className="overflow-hidden p-0">
            <button
              onClick={() => openOrder(order.id)}
              className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 p-4 text-left transition hover:bg-orange-50/60"
            >
              <span className="font-semibold text-stone-900">{formatDate(order.order_date)}</span>
              <span className="capitalize text-stone-600">{order.app_name}</span>
              <span className="text-sm text-stone-400">{order.order_id || 'No invoice ID'}</span>
              <span className="ml-auto font-bold text-stone-900">{rupees(order.total_amount)}</span>
            </button>
            {expanded === order.id && (
              <div className="border-t border-amber-900/10 bg-white/35 px-4 pb-4 pt-3">
                <p className="mb-3 text-xs text-stone-500">
                  Delivery fee {rupees(order.delivery_fee)} · Discount {rupees(order.discount)}
                  {order.notes ? ` · ${order.notes}` : ''}
                </p>
                {items.length > 0 ? (
                  <div className="space-y-1">
                    {items.map(item => (
                      <div key={item.id ?? `${item.name}-${item.quantity}`} className="flex justify-between gap-4 rounded-lg bg-white/55 px-3 py-2 text-sm">
                        <span className="text-stone-700">{item.name}{item.quantity ? ` · ${item.quantity}` : ''}</span>
                        <span className="whitespace-nowrap font-medium text-stone-900">{rupees(item.total_price)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-stone-400">No item details saved for this invoice.</p>
                )}
                <button
                  onClick={() => removeOrder(order.id)}
                  className="mt-3 rounded-lg bg-red-500/15 px-3 py-1.5 text-xs font-semibold text-red-700 transition hover:bg-red-500/25"
                >
                  Delete invoice
                </button>
              </div>
            )}
          </Card>
        ))}
        {!loading && !error && orders.length === 0 && (
          <Card className="py-10 text-center text-sm text-stone-400">No saved invoices found.</Card>
        )}
      </section>

      {total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-end gap-3 text-sm text-stone-600">
          <button
            onClick={() => setPage(current => Math.max(0, current - 1))}
            disabled={page === 0 || loading}
            className="rounded-xl bg-white/60 px-3 py-2 disabled:opacity-40"
          >
            Previous
          </button>
          <span>Page {page + 1} of {pageCount}</span>
          <button
            onClick={() => setPage(current => Math.min(pageCount - 1, current + 1))}
            disabled={page >= pageCount - 1 || loading}
            className="rounded-xl bg-white/60 px-3 py-2 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </>
  );
}
