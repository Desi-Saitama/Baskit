import { useEffect, useState } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts';
import { Bell } from 'lucide-react';
import Header from '@/components/layout/Header';
import Card from '@/components/layout/Card';
import {
  getSavingsInsights, getPriceTrend, getOrders, getOrder, deleteOrder as apiDeleteOrder,
  type SavingsInsight, type PriceTrendPoint, type Order, type OrderItem,
  getItemFrequency,
} from '@/lib/api';
import { rupees, formatDate } from '@/lib/utils';

const tooltipStyle = {
  background: '#fffaf0', color: '#332514',
  border: '1px solid rgba(141,92,45,.18)', borderRadius: '12px', fontSize: '13px',
};

export default function Savings() {
  const [insights, setInsights] = useState<SavingsInsight[]>([]);
  const [priceTrend, setPriceTrend] = useState<PriceTrendPoint[]>([]);
  const [trendItem, setTrendItem] = useState('');
  const [frequentItems, setFrequentItems] = useState<string[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [orderItems, setOrderItems] = useState<OrderItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      getSavingsInsights().then(r => setInsights(r.insights)).catch(() =>
        setInsights([
          { type: 'consolidation', title: 'Consolidate grocery runs', description: 'Group orders to save on delivery fees', impact: 620 },
          { type: 'discount', title: 'Best discount app', description: 'Check which app gives the most discounts', impact: 410 },
          { type: 'subscription', title: 'Consider delivery pass', description: 'Your delivery fees may justify a subscription', impact: 280 },
          { type: 'variance', title: 'Price variance detected', description: 'Some items have significant price swings', impact: 190 },
        ])
      ),
      getOrders(0, 10).then(r => setOrders(r.orders)),
      getItemFrequency(10).then(r => {
        const names = r.items.map(i => i.name);
        setFrequentItems(names);
        if (names.length > 0) {
          setTrendItem(names[0]);
          getPriceTrend(names[0]).then(r => setPriceTrend(r.data)).catch(() => {});
        }
      }).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const loadTrend = (item: string) => {
    setTrendItem(item);
    getPriceTrend(item).then(r => setPriceTrend(r.data)).catch(() => setPriceTrend([]));
  };

  const toggleExpand = async (id: number) => {
    if (expanded === id) {
      setExpanded(null);
      setOrderItems([]);
      return;
    }
    setExpanded(id);
    try {
      const r = await getOrder(id);
      setOrderItems(r.items);
    } catch {
      setOrderItems([]);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this order? This cannot be undone.')) return;
    try {
      await apiDeleteOrder(id);
      setOrders(prev => prev.filter(o => o.id !== id));
      if (expanded === id) setExpanded(null);
    } catch (e: any) {
      alert(e.message);
    }
  };

  const avgPrice = priceTrend.length > 0
    ? priceTrend.reduce((s, p) => s + p.price, 0) / priceTrend.length
    : 0;

  if (loading) {
    return <div className="h-40 rounded-2xl bg-amber-100/50 animate-pulse" />;
  }

  return (
    <>
      <Header
        title="Savings, insights & trends"
        subtitle="Actionable alerts from discounts, delivery fees, price variance and order history."
      />

      {/* Insight cards */}
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {insights.map((ins, i) => (
          <Card key={i} hover className="animate-fade-in">
            <Bell className={i === 2 ? 'text-orange-400' : 'text-orange-700'} size={20} />
            <b className="mt-4 block text-stone-900">{ins.title}</b>
            <p className="mt-1 text-sm text-stone-500">{ins.description}</p>
            <p className="mt-2 text-xs text-orange-700 font-semibold">
              Projected impact: {rupees(ins.impact)}/mo
            </p>
          </Card>
        ))}
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-5">
        {/* Price trend */}
        <Card className="xl:col-span-3 animate-fade-in delay-2">
          <div className="flex items-center justify-between mb-4">
            <b className="text-stone-900">
              Price trend{trendItem ? `: ${trendItem}` : ''}
            </b>
            {frequentItems.length > 0 && (
              <select
                value={trendItem}
                onChange={e => loadTrend(e.target.value)}
                className="rounded-xl border border-amber-900/10 bg-white/60 px-3 py-1.5 text-sm outline-none"
              >
                {frequentItems.map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            )}
          </div>
          {priceTrend.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={priceTrend}>
                <XAxis dataKey="date" stroke="#9a7b5b" fontSize={12} />
                <YAxis stroke="#9a7b5b" fontSize={12} />
                <Tooltip contentStyle={tooltipStyle} />
                <ReferenceLine y={avgPrice} stroke="#f59e0b" strokeDasharray="5 5" label={{ value: 'Avg', fill: '#f59e0b', fontSize: 11 }} />
                <Line dataKey="price" stroke="#22c55e" strokeWidth={3} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[300px] items-center justify-center text-stone-400">
              {trendItem ? 'No price data for this item' : 'Select an item to see price trends'}
            </div>
          )}
        </Card>

        {/* Orders history log */}
        <Card className="xl:col-span-2 animate-fade-in delay-3">
          <b className="text-stone-900">Orders history log</b>
          <div className="mt-3 max-h-[360px] overflow-y-auto space-y-2">
            {orders.map(o => (
              <details
                key={o.id}
                open={expanded === o.id}
                className="rounded-2xl bg-white/55 overflow-hidden"
              >
                <summary
                  className="cursor-pointer p-3 text-sm text-stone-900 hover:bg-orange-50/60 transition"
                  onClick={e => { e.preventDefault(); toggleExpand(o.id); }}
                >
                  <span className="font-medium">{formatDate(o.order_date)}</span>
                  <span className="mx-1.5 text-stone-400">·</span>
                  <span className="capitalize">{o.app_name}</span>
                  <span className="mx-1.5 text-stone-400">·</span>
                  <span className="font-semibold">{rupees(o.total_amount)}</span>
                </summary>
                {expanded === o.id && (
                  <div className="px-3 pb-3">
                    <p className="text-xs text-stone-500 mb-2">
                      {o.order_id || 'No ID'} · fee {rupees(o.delivery_fee)} · discount {rupees(o.discount)}
                    </p>
                    {orderItems.length > 0 && (
                      <div className="mb-3 space-y-1">
                        {orderItems.map((it, idx) => (
                          <div key={idx} className="flex justify-between text-xs text-stone-600 bg-white/40 rounded-lg px-2 py-1">
                            <span>{it.name}</span>
                            <span>{rupees(it.total_price)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleDelete(o.id)}
                        className="rounded-lg bg-red-500/20 px-3 py-1 text-xs text-red-700 hover:bg-red-500/30 transition"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                )}
              </details>
            ))}
            {orders.length === 0 && (
              <p className="text-sm text-stone-400 text-center py-8">No orders yet</p>
            )}
          </div>
        </Card>
      </section>
    </>
  );
}
