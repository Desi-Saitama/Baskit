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
  getSpendingOverTime, getDailyHeatmap, getMonthlyStats, getAvailableMonths,
  type StatsSummary, type AppStat, type CategoryStat,
  type SpendPoint, type HeatmapPoint, type MonthlyStatsResponse, type AvailableMonth, healthCheck,
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
  const [monthly, setMonthly] = useState<MonthlyStatsResponse | null>(null);
  const [availableMonths, setAvailableMonths] = useState<AvailableMonth[]>([]);
  const [selectedMonth, setSelectedMonth] = useState('');
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
      getMonthlyStats(24, true).then(setMonthly).catch(() => setMonthly(null)),
      getAvailableMonths().then(r => {
        setAvailableMonths(r.months);
        setSelectedMonth(r.months[0]?.month ?? '');
      }).catch(() => {}),
      healthCheck().then(() => setApiOk(true)).catch(() => setApiOk(false)),
    ]).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    getSpendingOverTime(period).then(r => setSpend(r.data)).catch(() => {});
  }, [period]);

  useEffect(() => {
    if (!selectedMonth) return;
    Promise.all([
      getStatsByApp(selectedMonth).then(r => setApps(r.apps)),
      getStatsByCategory(selectedMonth).then(r => setCategories(r.categories)),
    ]).catch(() => {});
  }, [selectedMonth]);

  const selectedMonthLabel = availableMonths.find(m => m.month === selectedMonth)?.label ?? 'All time';

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

  const comparisonText = monthly?.comparison.spend_delta_percent == null
    ? 'No last-month baseline yet'
    : `${monthly.comparison.spend_delta_percent >= 0 ? '+' : ''}${monthly.comparison.spend_delta_percent.toFixed(1)}% vs last month`;
  const comparisonTone = (monthly?.comparison.spend_delta ?? 0) <= 0
    ? 'text-emerald-700 bg-emerald-100'
    : 'text-orange-800 bg-orange-100';
  const maxMonthlySpend = Math.max(...(monthly?.months.map(m => m.total_spend) ?? [0]), 1);

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
        title="Baskit — Your Spend Command Centre"
        subtitle="Upload receipts, normalize noisy OCR items, and watch delivery app spending patterns across groceries and food."
        actions={
          <>
            <label className="flex items-center gap-2 rounded-full bg-white/60 px-3 py-2 text-sm text-stone-700">
              <span className="hidden sm:inline">Month</span>
              <select
                value={selectedMonth}
                onChange={e => setSelectedMonth(e.target.value)}
                disabled={availableMonths.length === 0}
                className="bg-transparent font-semibold outline-none"
              >
                {availableMonths.length === 0 && <option>All recorded data</option>}
                {availableMonths.map(month => <option key={month.month} value={month.month}>{month.label}</option>)}
              </select>
            </label>
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

      {monthly && (
        <section className="mt-4 grid gap-4 xl:grid-cols-3">
          <Card className="xl:col-span-2 animate-fade-in delay-2">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <b className="text-stone-900">Monthly expense separation</b>
                <p className="mt-1 text-sm text-stone-500">Only months with recorded orders are shown. {selectedMonthLabel} filters the app and category views below.</p>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${comparisonTone}`}>
                {comparisonText}
              </span>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={monthly.months}>
                <CartesianGrid stroke="rgba(141,92,45,.16)" />
                <XAxis dataKey="label" stroke="#9a7b5b" fontSize={12} />
                <YAxis stroke="#9a7b5b" fontSize={12} />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value) => rupees(Number(value ?? 0))}
                />
                <Bar dataKey="total_spend" fill="#c05621" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>

          <Card className="animate-fade-in delay-3">
            <b className="text-stone-900">This month vs last month</b>
            <div className="mt-4 grid gap-3">
              <div className="rounded-xl bg-white/60 p-4">
                <p className="text-xs uppercase tracking-wide text-stone-500">This month</p>
                <div className="mt-1 flex items-end justify-between gap-3">
                  <b className="text-2xl text-stone-900">{rupees(monthly.current_month.total_spend)}</b>
                  <span className="text-sm text-stone-500">{monthly.current_month.total_orders} orders</span>
                </div>
                <p className="mt-1 text-xs text-stone-500">Avg {rupees(monthly.current_month.avg_order)} per order</p>
              </div>
              <div className="rounded-xl bg-white/60 p-4">
                <p className="text-xs uppercase tracking-wide text-stone-500">Last month</p>
                <div className="mt-1 flex items-end justify-between gap-3">
                  <b className="text-2xl text-stone-900">{rupees(monthly.previous_month.total_spend)}</b>
                  <span className="text-sm text-stone-500">{monthly.previous_month.total_orders} orders</span>
                </div>
                <p className="mt-1 text-xs text-stone-500">Avg {rupees(monthly.previous_month.avg_order)} per order</p>
              </div>
              <div className="rounded-xl border border-orange-200 bg-orange-50/70 p-4">
                <p className="text-sm text-stone-600">Difference</p>
                <b className="mt-1 block text-xl text-stone-900">
                  {monthly.comparison.spend_delta >= 0 ? '+' : ''}{rupees(monthly.comparison.spend_delta)}
                </b>
                <p className="mt-1 text-xs text-stone-500">
                  {monthly.comparison.orders_delta >= 0 ? '+' : ''}{monthly.comparison.orders_delta} orders,
                  {' '}avg order {monthly.comparison.avg_order_delta >= 0 ? '+' : ''}{rupees(monthly.comparison.avg_order_delta)}
                </p>
              </div>
            </div>
          </Card>

          <Card className="xl:col-span-3 animate-fade-in delay-4">
            <b className="text-stone-900">Month-wise expense list</b>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {monthly.months.slice().reverse().map(m => (
                <div key={m.month} className="rounded-xl bg-white/60 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <b className="text-sm text-stone-900">{m.label}</b>
                      <p className="text-xs text-stone-500">{m.total_orders} orders</p>
                    </div>
                    <b className="text-lg text-orange-800">{rupees(m.total_spend)}</b>
                  </div>
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-amber-100">
                    <div
                      className="h-full rounded-full bg-orange-700"
                      style={{ width: `${Math.max((m.total_spend / maxMonthlySpend) * 100, m.total_spend > 0 ? 6 : 0)}%` }}
                    />
                  </div>
                  <div className="mt-2 flex justify-between text-xs text-stone-500">
                    <span>Saved {rupees(m.total_saved)}</span>
                    <span>Fees {rupees(m.total_fees)}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </section>
      )}

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
          <b className="text-stone-900">App spend share · {selectedMonthLabel}</b>
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
          <b className="text-stone-900">Spend by category · {selectedMonthLabel}</b>
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
