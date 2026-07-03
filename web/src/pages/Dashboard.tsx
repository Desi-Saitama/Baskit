import { useEffect, useState, useMemo } from 'react';
import {
  ResponsiveContainer, ComposedChart, Bar, Line, CartesianGrid, XAxis, YAxis, Tooltip,
  PieChart, Pie, Cell, BarChart,
} from 'recharts';
import { Activity } from 'lucide-react';
import Header from '@/components/layout/Header';
import Card from '@/components/layout/Card';
import MiniBar from '@/components/charts/MiniBar';
import {
  getSummary, getStatsByApp, getStatsByCategory,
  getSpendingOverTime, getDailyHeatmap,
  type StatsSummary, type AppStat, type CategoryStat,
  type SpendPoint, type HeatmapPoint, healthCheck,
} from '@/lib/api';
import { rupees } from '@/lib/utils';

const tooltipStyle = {
  background: '#fffaf0',
  color: '#332514',
  border: '1px solid rgba(141,92,45,.18)',
  borderRadius: '12px',
  fontSize: '13px',
};

export default function Dashboard() {
  const [summary, setSummary] = useState<StatsSummary | null>(null);
  const [apps, setApps] = useState<AppStat[]>([]);
  const [categories, setCategories] = useState<CategoryStat[]>([]);
  const [spend, setSpend] = useState<SpendPoint[]>([]);
  const [heatmap, setHeatmap] = useState<HeatmapPoint[]>([]);
  const [period, setPeriod] = useState<'weekly' | 'daily' | 'monthly'>('weekly');
  const [loading, setLoading] = useState(true);
  const [apiOk, setApiOk] = useState<boolean | null>(null);

  useEffect(() => {
    Promise.allSettled([
      getSummary().then(setSummary),
      getStatsByApp().then(r => setApps(r.apps)),
      getStatsByCategory().then(r => setCategories(r.categories)),
      getSpendingOverTime(period).then(r => setSpend(r.data)).catch(() => setSpend([])),
      getDailyHeatmap().then(r => setHeatmap(r.data)).catch(() => setHeatmap([])),
      healthCheck().then(() => setApiOk(true)).catch(() => setApiOk(false)),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    getSpendingOverTime(period).then(r => setSpend(r.data)).catch(() => {});
  }, [period]);

  const pie = useMemo(
    () => apps.map(a => ({
      name: a.app_name,
      value: a.total_spent,
      color: ({
        zepto: '#8b5cf6', blinkit: '#f59e0b', instamart: '#16a34a',
        swiggy: '#ea580c', zomato: '#ef4444', bigbasket: '#84cc16', jiomart: '#2563eb',
      } as Record<string, string>)[a.app_name.toLowerCase()] || '#8b5cf6',
    })),
    [apps]
  );

  const kpis = summary ? [
    { label: 'Today', value: rupees(summary.today_spend), color: '#8b5cf6' },
    { label: 'This Week', value: rupees(summary.week_spend), color: '#8b5cf6' },
    { label: 'This Month', value: rupees(summary.month_spend), color: '#8b5cf6' },
    { label: 'All Time', value: rupees(summary.total_spend), color: '#8b5cf6' },
    { label: 'Total Saved', value: rupees(summary.total_saved), color: '#22c55e' },
    { label: 'Total Orders', value: String(summary.total_orders), color: '#8b5cf6' },
    { label: 'Avg Order', value: rupees(summary.avg_order), color: '#8b5cf6' },
    { label: 'Delivery Fees', value: rupees(summary.total_fees), color: '#ea580c' },
  ] : [];

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-28 rounded-2xl bg-amber-100/50 animate-pulse" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-32 rounded-2xl bg-amber-100/50 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <>
      <Header
        title="Command centre for every kharcha"
        subtitle="Upload receipts, normalize noisy OCR items, and watch delivery app spending patterns across groceries and food."
        actions={
          <>
            <button className="rounded-full bg-white/60 px-4 py-2 text-sm text-stone-900 hover:bg-amber-100 transition">
              {apiOk === true ? '✅' : apiOk === false ? '❌' : '⏳'} /api/health {apiOk === true ? 'ok' : apiOk === false ? 'error' : '...'}
            </button>
          </>
        }
      />

      {/* KPI Cards */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {kpis.map((k, i) => (
          <Card key={k.label} hover className={`animate-fade-in delay-${i + 1}`}>
            <p className="text-sm text-stone-500">{k.label}</p>
            <div className="mt-2 flex items-end justify-between">
              <b className="text-2xl text-stone-900">{k.value}</b>
              <Activity className="text-orange-700 opacity-70 size-5" />
            </div>
            <MiniBar color={k.color} />
          </Card>
        ))}
      </section>

      {/* Charts row */}
      <section className="mt-4 grid gap-4 xl:grid-cols-3">
        {/* Spending over time */}
        <Card className="xl:col-span-2 animate-fade-in delay-3">
          <div className="mb-4 flex justify-between items-center">
            <b className="text-stone-900">Spending over time</b>
            <div className="rounded-full bg-white/60 p-1 text-xs flex">
              {(['weekly', 'daily', 'monthly'] as const).map(p => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`rounded-full px-3 py-1 capitalize transition ${
                    period === p
                      ? 'bg-orange-600 text-white shadow'
                      : 'text-stone-600 hover:text-stone-900'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={310}>
            <ComposedChart data={spend}>
              <CartesianGrid stroke="rgba(141,92,45,.16)" />
              <XAxis dataKey="label" stroke="#9a7b5b" fontSize={12} />
              <YAxis stroke="#9a7b5b" fontSize={12} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="spend" fill="#8b5cf6" radius={[8, 8, 0, 0]} />
              <Line dataKey="avg" stroke="#f59e0b" strokeWidth={3} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>

        {/* App share pie */}
        <Card className="animate-fade-in delay-4">
          <b className="text-stone-900">App spend share</b>
          {pie.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={pie}
                  dataKey="value"
                  innerRadius={70}
                  outerRadius={105}
                  paddingAngle={2}
                >
                  {pie.map((p) => (
                    <Cell key={p.name} fill={p.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[300px] items-center justify-center text-stone-400">
              No data yet
            </div>
          )}
          <div className="flex flex-wrap gap-2 mt-2">
            {pie.map(p => (
              <span key={p.name} className="flex items-center gap-1.5 text-xs text-stone-600">
                <span className="size-2.5 rounded-full" style={{ background: p.color }} />
                {p.name}
              </span>
            ))}
          </div>
        </Card>

        {/* Category bar */}
        <Card className="animate-fade-in delay-5">
          <b className="text-stone-900">Spend by category</b>
          {categories.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart layout="vertical" data={categories.slice(0, 8)}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="category" width={110} stroke="#9a7b5b" fontSize={12} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="total_spent" fill="#22c55e" radius={8} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[260px] items-center justify-center text-stone-400">
              No data yet
            </div>
          )}
        </Card>

        {/* Heatmap */}
        <Card className="xl:col-span-2 animate-fade-in delay-6">
          <b className="text-stone-900">Daily spend heatmap</b>
          <div className="mt-5 grid grid-cols-10 gap-2">
            {(heatmap.length > 0 ? heatmap : Array.from({ length: 30 }, (_, i) => ({ date: `Day ${i + 1}`, amount: 0 }))).slice(0, 30).map((d, i) => {
              const intensity = heatmap.length > 0 && d.amount > 0
                ? Math.min(d.amount / (Math.max(...heatmap.map(h => h.amount)) || 1), 1)
                : 0;
              return (
                <div
                  key={i}
                  className="h-12 rounded-xl border border-white/5 flex items-start"
                  style={{
                    backgroundColor: intensity > 0.7
                      ? 'rgba(234,88,12,0.6)'
                      : intensity > 0.4
                        ? 'rgba(245,158,11,0.5)'
                        : intensity > 0.15
                          ? 'rgba(234,124,12,0.35)'
                          : 'rgba(245,222,179,0.5)',
                  }}
                  title={`${d.date}: ₹${d.amount}`}
                >
                  <span className="p-1.5 font-mono text-[10px] text-stone-500">{i + 1}</span>
                </div>
              );
            })}
          </div>
        </Card>
      </section>
    </>
  );
}
