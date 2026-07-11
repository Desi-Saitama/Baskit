import { useEffect, useState } from 'react';
import { KeyRound } from 'lucide-react';
import Header from '@/components/layout/Header';
import Card from '@/components/layout/Card';
import { getKeyPoolStatus, updatePassword, type KeyPoolStatus } from '@/lib/api';

export default function SettingsPage() {
  const [keys, setKeys] = useState<KeyPoolStatus[]>([]);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(true);
  const [keyPoolError, setKeyPoolError] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    getKeyPoolStatus()
      .then(r => setKeys(r.keys))
      .catch((e: Error) => setKeyPoolError(e.message || 'Could not load key usage.'))
      .finally(() => setLoading(false));
  }, []);

  const handlePasswordUpdate = async () => {
    setMsg(null);
    if (!newPassword) {
      setMsg({ text: 'Password cannot be empty', type: 'error' });
      return;
    }
    if (newPassword !== confirmPassword) {
      setMsg({ text: 'Passwords do not match', type: 'error' });
      return;
    }
    try {
      await updatePassword(newPassword);
      setMsg({ text: 'Password updated successfully', type: 'success' });
      setNewPassword('');
      setConfirmPassword('');
    } catch (e: any) {
      setMsg({ text: e.message, type: 'error' });
    }
  };

  const handleCSVExport = (type: 'orders' | 'items') => {
    const token = localStorage.getItem('kharcha_token');
    const url = `/api/export/${type}-csv`;
    // Use direct download via anchor
    const a = document.createElement('a');
    a.href = url;
    a.download = `${type}.csv`;
    // For auth, we fetch and create blob URL
    fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.blob())
      .then(blob => {
        const blobUrl = URL.createObjectURL(blob);
        a.href = blobUrl;
        a.click();
        URL.revokeObjectURL(blobUrl);
      })
      .catch(e => alert('Export failed: ' + e.message));
  };

  if (loading) {
    return <div className="h-40 rounded-2xl bg-amber-100/50 animate-pulse" />;
  }

  return (
    <>
      <Header
        title="Settings & key pool"
        subtitle="Monitor Gemini key limits, update credentials and export local SQLite data."
      />

      {/* Key pool status */}
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {keys.map((k, i) => (
          <Card key={i} hover className="animate-fade-in">
            <KeyRound className="text-orange-700" size={20} />
            <b className="mt-4 block text-stone-900">
              Key {String(k.index).padStart(2, '0')} · {k.suffix}
            </b>
            <p className="text-sm text-stone-500">
              {k.count}/20 used today
              {k.active && <span className="ml-2 text-green-600 text-xs font-semibold">● Active</span>}
              {k.exhausted && <span className="ml-2 text-red-500 text-xs font-semibold">● Exhausted</span>}
            </p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/60">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  k.exhausted ? 'bg-red-500' : k.active ? 'bg-green-500' : 'bg-orange-500'
                }`}
                style={{ width: `${(k.count / 20) * 100}%` }}
              />
            </div>
          </Card>
        ))}
        {!keys.length && !keyPoolError && (
          <Card className="md:col-span-2 xl:col-span-4 text-sm text-stone-500">
            No Gemini API keys are configured on this server.
          </Card>
        )}
        {keyPoolError && (
          <Card className="md:col-span-2 xl:col-span-4 text-sm text-red-700">
            {keyPoolError}
          </Card>
        )}
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-2">
        {/* Password update */}
        <Card className="animate-fade-in delay-2">
          <b className="text-stone-900">Credentials manager</b>
          {msg && (
            <div className={`mt-3 rounded-xl p-3 text-sm ${
              msg.type === 'success' ? 'bg-green-500/10 text-green-700' : 'bg-red-500/10 text-red-700'
            }`}>
              {msg.text}
            </div>
          )}
          <input
            type="password"
            placeholder="New password"
            value={newPassword}
            onChange={e => setNewPassword(e.target.value)}
            className="mt-4 w-full rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-3 text-sm outline-none focus:ring-2 focus:ring-orange-300"
          />
          <input
            type="password"
            placeholder="Confirm password"
            value={confirmPassword}
            onChange={e => setConfirmPassword(e.target.value)}
            className="mt-3 w-full rounded-xl border border-amber-900/10 bg-[var(--input)] px-3 py-3 text-sm outline-none focus:ring-2 focus:ring-orange-300"
          />
          <button
            onClick={handlePasswordUpdate}
            className="mt-4 rounded-xl bg-[var(--primary)] px-5 py-2.5 text-sm text-[var(--primary-foreground)] font-semibold hover:opacity-90 transition"
          >
            Update Password
          </button>
        </Card>

        {/* CSV exporter */}
        <Card className="animate-fade-in delay-3">
          <b className="text-stone-900">CSV exporter</b>
          <p className="mt-2 text-sm text-stone-500">
            Download your data as CSV files for backup or analysis.
          </p>
          <div className="mt-4 flex gap-3">
            <button
              onClick={() => handleCSVExport('orders')}
              className="rounded-xl bg-white/60 px-4 py-2 text-sm text-stone-700 hover:bg-white/80 transition shadow"
            >
              📄 orders.csv
            </button>
            <button
              onClick={() => handleCSVExport('items')}
              className="rounded-xl bg-white/60 px-4 py-2 text-sm text-stone-700 hover:bg-white/80 transition shadow"
            >
              📄 items.csv
            </button>
          </div>
        </Card>
      </section>
    </>
  );
}
