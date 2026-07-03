import { useEffect, useState } from 'react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell,
} from 'recharts';
import { Search } from 'lucide-react';
import Header from '@/components/layout/Header';
import Card from '@/components/layout/Card';
import {
  getStatsByApp, getItemFrequency, getTopItems, getItemsPerApp,
  type AppStat, type ItemFrequency,
} from '@/lib/api';
import { rupees, appColor } from '@/lib/utils';

const tooltipStyle = {
  background: '#fffaf0', color: '#332514',
  border: '1px solid rgba(141,92,45,.18)', borderRadius: '12px', fontSize: '13px',
};

export default function AppsItems() {
  const [apps, setApps] = useState<AppStat[]>([]);
  const [items, setItems] = useState<ItemFrequency[]>([]);
  const [topItems, setTopItems] = useState<ItemFrequency[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      getStatsByApp().then(r => setApps(r.apps)),
      getItemFrequency(20).then(r => setItems(r.items)).catch(() => {}),
      getTopItems(10).then(r => setTopItems(r.items)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const pie = apps.map(a => ({
    name: a.app_name, value: a.total_spent, color: appColor(a.app_name),
  }));

  const filtered = items.filter(i =>
    !search || i.name.toLowerCase().includes(search.toLowerCase()) ||
    i.brand.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return <div className="h-40 rounded-2xl bg-amber-100/50 animate-pulse" />;
  }

  return (
    <>
      <Header
        title="App-wise analysis & item intelligence"
        subtitle="Compare Zepto, Blinkit, Instamart, BigBasket, JioMart, Swiggy and Zomato, then drill into recurring items."
      />

      {/* App cards */}
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {apps.map(a => (
          <Card key={a.app_name} hover className="animate-fade-in">
            <div className="mb-3 flex items-center gap-2">
              <span className="size-3 rounded-full" style={{ background: appColor(a.app_name) }} />
              <b className="text-stone-900 capitalize">{a.app_name}</b>
            </div>
            <p className="text-2xl font-bold text-stone-900">{rupees(a.total_spent)}</p>
            <p className="text-sm text-stone-500">
              {a.orders} orders · {rupees(a.total_saved)} saved ·{' '}
              {a.total_saved + a.total_spent > 0
                ? Math.round((a.total_saved / (a.total_saved + a.total_spent)) * 100)
                : 0}% discount
            </p>
          </Card>
        ))}
      </section>

      {/* Charts */}
      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        {/* Spend vs delivery fees */}
        <Card className="animate-fade-in delay-2">
          <b className="text-stone-900">Spend vs delivery fees</b>
          <ResponsiveContainer width="100%" height={290}>
            <BarChart data={apps}>
              <XAxis dataKey="app_name" stroke="#9a7b5b" fontSize={12} />
              <YAxis stroke="#9a7b5b" fontSize={12} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="total_spent" fill="#8b5cf6" radius={8} name="Spent" />
              <Bar dataKey="total_fees" fill="#ea580c" radius={8} name="Fees" />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Frequent purchases */}
        <Card className="animate-fade-in delay-3">
          <b className="text-stone-900">Frequent purchases</b>
          {topItems.length > 0 ? (
            <ResponsiveContainer width="100%" height={290}>
              <BarChart layout="vertical" data={topItems.slice(0, 8)}>
                <XAxis type="number" hide />
                <YAxis dataKey="name" type="category" width={140} stroke="#9a7b5b" fontSize={12} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="times" fill="#f59e0b" radius={8} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[290px] items-center justify-center text-stone-400">
              No item data yet
            </div>
          )}
        </Card>
      </section>

      {/* Searchable item directory */}
      <Card className="mt-4 overflow-hidden animate-fade-in delay-4">
        <div className="mb-4 flex items-center justify-between">
          <b className="text-stone-900">Searchable item directory</b>
          <div className="flex items-center gap-2 rounded-xl bg-white/60 px-3 py-2 text-sm text-stone-500">
            <Search size={16} />
            <input
              type="text"
              placeholder="coke, amul, paneer..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="bg-transparent outline-none placeholder:text-stone-400 w-40"
            />
          </div>
        </div>
        <div className="overflow-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="font-mono text-xs uppercase tracking-widest text-stone-400">
              <tr>
                {['Item', 'Brand', 'Category', 'Times', 'Avg Price', 'Range', 'Spent'].map(h => (
                  <th className="border-b border-amber-900/10 py-3 px-2" key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length > 0 ? filtered.map(r => (
                <tr className="hover:bg-orange-50/80 transition" key={r.name}>
                  <td className="py-3 px-2 text-stone-900 font-medium">{r.name}</td>
                  <td className="px-2 text-stone-600">{r.brand}</td>
                  <td className="px-2 text-stone-600">{r.category}</td>
                  <td className="px-2">{r.times}</td>
                  <td className="px-2">{rupees(r.avg_price)}</td>
                  <td className="px-2 text-stone-500">{rupees(r.min_price)}–{rupees(r.max_price)}</td>
                  <td className="px-2 font-medium">{rupees(r.total_spent)}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-stone-400">
                    {search ? 'No items match your search' : 'No item data yet — upload invoices to get started'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
