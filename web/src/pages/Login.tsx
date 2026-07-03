import { useState } from 'react';
import { ReceiptText } from 'lucide-react';
import { login, register, saveToken } from '@/lib/api';

interface LoginProps {
  onLogin: () => void;
}

export default function Login({ onLogin }: LoginProps) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isRegister, setIsRegister] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) {
      setError('Password cannot be empty');
      return;
    }
    if (isRegister && password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const fn = isRegister ? register : login;
      const res = await fn(username, password);
      saveToken(res.access_token);
      onLogin();
    } catch (e: any) {
      if (e.message?.includes('No account exists')) {
        setIsRegister(true);
        setError('No account exists. Create one below.');
      } else {
        setError(e.message || 'Login failed');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-main flex items-center justify-center p-4">
      <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_18%_5%,rgba(245,158,11,.24),transparent_30%),radial-gradient(circle_at_82%_10%,rgba(139,92,246,.16),transparent_26%),radial-gradient(circle_at_55%_90%,rgba(34,197,94,.13),transparent_28%),linear-gradient(135deg,#fff7ea,#fffaf0_54%,#f7ead8)]" />

      <div className="w-full max-w-md animate-fade-in">
        <div className="text-center mb-8">
          <div className="mx-auto mb-4 grid size-16 place-items-center rounded-3xl bg-gradient-to-br from-orange-500 to-amber-400 text-white shadow-xl shadow-orange-300/40">
            <ReceiptText className="size-8" />
          </div>
          <h1 className="text-3xl font-extrabold text-stone-900 font-heading">Kharcha Tracker</h1>
          <p className="mt-1 text-sm text-stone-500">Your private expense tracker for Indian delivery apps</p>
        </div>

        <div className="glass-card">
          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <p className="text-sm text-amber-700 bg-amber-100/70 rounded-xl p-3">
                👋 First time setup — create your account below.
              </p>
            )}

            <div>
              <label className="text-sm font-semibold text-stone-700">Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="admin"
                className="mt-1 w-full rounded-xl border border-amber-900/10 bg-[var(--input)] px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-orange-300 transition"
              />
            </div>

            <div>
              <label className="text-sm font-semibold text-stone-700">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Enter password"
                className="mt-1 w-full rounded-xl border border-amber-900/10 bg-[var(--input)] px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-orange-300 transition"
              />
            </div>

            {isRegister && (
              <div>
                <label className="text-sm font-semibold text-stone-700">Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  placeholder="Confirm password"
                  className="mt-1 w-full rounded-xl border border-amber-900/10 bg-[var(--input)] px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-orange-300 transition"
                />
              </div>
            )}

            {error && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-2xl bg-gradient-to-r from-orange-600 to-amber-500 py-3 text-white font-bold shadow-lg shadow-orange-300/40 hover:shadow-xl hover:shadow-orange-300/50 transition-all disabled:opacity-50"
            >
              {loading ? '⏳' : isRegister ? '🚀 Create Account & Sign In' : '🔓 Sign In'}
            </button>

            {!isRegister && (
              <button
                type="button"
                onClick={() => setIsRegister(true)}
                className="w-full text-sm text-stone-500 hover:text-orange-700 transition"
              >
                First time? Create an account
              </button>
            )}
          </form>
        </div>
      </div>
    </div>
  );
}
