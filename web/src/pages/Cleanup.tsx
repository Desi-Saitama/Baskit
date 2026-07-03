import { useEffect, useState } from 'react';
import { Trash2 } from 'lucide-react';
import Header from '@/components/layout/Header';
import Card from '@/components/layout/Card';
import {
  getCleanupClusters, getAliases, mergeItems, deleteAlias,
  type DuplicateCluster, type ItemAlias,
} from '@/lib/api';
import { CATEGORIES } from '@/lib/utils';

export default function Cleanup() {
  const [clusters, setClusters] = useState<DuplicateCluster[]>([]);
  const [aliases, setAliases] = useState<ItemAlias[]>([]);
  const [loading, setLoading] = useState(true);
  const [merging, setMerging] = useState<number | null>(null);

  // Merge form state per cluster
  const [mergeData, setMergeData] = useState<Record<number, {
    canonical_name: string;
    canonical_brand: string;
    canonical_cat: string;
  }>>({});

  useEffect(() => {
    Promise.allSettled([
      getCleanupClusters().then(r => {
        setClusters(r.clusters);
        // Initialize merge data
        const init: typeof mergeData = {};
        r.clusters.forEach((c, i) => {
          init[i] = {
            canonical_name: c.canonical_suggestion || c.variants[0] || '',
            canonical_brand: c.brand_suggestions?.[0] || '',
            canonical_cat: c.category_suggestions?.[0] || '',
          };
        });
        setMergeData(init);
      }).catch(() => setClusters([])),
      getAliases().then(r => setAliases(r.aliases)).catch(() => setAliases([])),
    ]).finally(() => setLoading(false));
  }, []);

  const handleMerge = async (idx: number) => {
    const cluster = clusters[idx];
    const data = mergeData[idx];
    if (!data) return;
    setMerging(idx);
    try {
      await mergeItems({
        variants: cluster.variants,
        canonical_name: data.canonical_name,
        canonical_brand: data.canonical_brand,
        canonical_cat: data.canonical_cat,
      });
      setClusters(prev => prev.filter((_, i) => i !== idx));
      // Refresh aliases
      getAliases().then(r => setAliases(r.aliases)).catch(() => {});
    } catch (e: any) {
      alert(e.message);
    } finally {
      setMerging(null);
    }
  };

  const handleDeleteAlias = async (id: number) => {
    try {
      await deleteAlias(id);
      setAliases(prev => prev.filter(a => a.id !== id));
    } catch (e: any) {
      alert(e.message);
    }
  };

  if (loading) {
    return <div className="h-40 rounded-2xl bg-amber-100/50 animate-pulse" />;
  }

  return (
    <>
      <Header
        title="Data cleanup interface"
        subtitle="Merge fuzzy OCR variants, repair category conflicts and manage alias mappings."
      />

      <section className="grid gap-4 xl:grid-cols-2">
        {/* Duplicate clusters */}
        <div className="space-y-4">
          {clusters.length > 0 ? clusters.map((cluster, idx) => (
            <Card key={idx} className="animate-fade-in">
              <b className="text-stone-900">
                Suspected duplicate cluster · {Math.round(cluster.score * 100)}%
              </b>
              {cluster.variants.map(v => (
                <p key={v} className="mt-2 rounded-xl bg-white/55 p-3 text-sm text-stone-700">{v}</p>
              ))}
              <div className="mt-4 grid gap-2 md:grid-cols-3">
                <input
                  placeholder="Canonical name"
                  value={mergeData[idx]?.canonical_name || ''}
                  onChange={e => setMergeData(prev => ({
                    ...prev, [idx]: { ...prev[idx], canonical_name: e.target.value }
                  }))}
                  className="rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-300"
                />
                <input
                  placeholder="Brand"
                  value={mergeData[idx]?.canonical_brand || ''}
                  onChange={e => setMergeData(prev => ({
                    ...prev, [idx]: { ...prev[idx], canonical_brand: e.target.value }
                  }))}
                  className="rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-300"
                />
                <select
                  value={mergeData[idx]?.canonical_cat || ''}
                  onChange={e => setMergeData(prev => ({
                    ...prev, [idx]: { ...prev[idx], canonical_cat: e.target.value }
                  }))}
                  className="rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-orange-300"
                >
                  <option value="">Category</option>
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <button
                onClick={() => handleMerge(idx)}
                disabled={merging === idx}
                className="mt-3 rounded-xl bg-[var(--primary)] px-4 py-2 text-sm text-[var(--primary-foreground)] font-semibold hover:opacity-90 transition disabled:opacity-50"
              >
                {merging === idx ? 'Merging...' : 'Merge Variants'}
              </button>
            </Card>
          )) : (
            <Card>
              <p className="text-center text-stone-400 py-8">
                ✨ No duplicate clusters detected. Your data is clean!
              </p>
            </Card>
          )}
        </div>

        {/* Saved mappings */}
        <Card className="animate-fade-in delay-1">
          <b className="text-stone-900">Saved mappings</b>
          <div className="mt-3 max-h-[500px] overflow-y-auto space-y-2">
            {aliases.length > 0 ? aliases.map(a => (
              <div key={a.id} className="flex items-center justify-between rounded-xl bg-white/55 p-3 text-sm">
                <div>
                  <span className="text-stone-600">{a.raw_name}</span>
                  <span className="mx-2 text-stone-400">→</span>
                  <span className="font-medium text-stone-900">{a.canonical_name}</span>
                  {a.canonical_brand && (
                    <span className="ml-2 text-xs text-stone-400">({a.canonical_brand})</span>
                  )}
                </div>
                <button
                  onClick={() => handleDeleteAlias(a.id)}
                  className="text-red-300 hover:text-red-500 transition"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            )) : (
              <p className="text-center text-stone-400 py-8">No alias mappings saved yet</p>
            )}
          </div>
        </Card>
      </section>
    </>
  );
}
