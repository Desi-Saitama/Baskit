import { useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Dashboard from '@/pages/Dashboard';
import AppsItems from '@/pages/AppsItems';
import Savings from '@/pages/Savings';
import Upload from '@/pages/Upload';
import BulkImport from '@/pages/BulkImport';
import Cleanup from '@/pages/Cleanup';
import SettingsPage from '@/pages/Settings';
import Login from '@/pages/Login';
import { isLoggedIn, clearToken } from '@/lib/api';

export default function App() {
  const [authenticated, setAuthenticated] = useState(isLoggedIn());
  const [page, setPage] = useState('Dashboard');

  const handleLogin = () => setAuthenticated(true);

  const handleLogout = () => {
    clearToken();
    setAuthenticated(false);
  };

  if (!authenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-amber-300/50">
      {/* Background gradient */}
      <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_18%_5%,rgba(245,158,11,.24),transparent_30%),radial-gradient(circle_at_82%_10%,rgba(139,92,246,.16),transparent_26%),radial-gradient(circle_at_55%_90%,rgba(34,197,94,.13),transparent_28%),linear-gradient(135deg,#fff7ea,#fffaf0_54%,#f7ead8)]" />

      <Sidebar page={page} onNavigate={setPage} />

      <main className="p-4 pt-16 lg:ml-72 lg:p-8 lg:pt-8">
        {/* Logout button */}
        <div className="fixed top-4 right-4 z-30">
          <button
            onClick={handleLogout}
            className="rounded-full bg-white/60 px-4 py-2 text-sm text-stone-600 hover:bg-red-50 hover:text-red-700 transition backdrop-blur-sm"
          >
            🚪 Sign Out
          </button>
        </div>

        {page === 'Dashboard' && <Dashboard />}
        {page === 'Apps & Items' && <AppsItems />}
        {page === 'Savings' && <Savings />}
        {page === 'Upload' && <Upload />}
        {page === 'Bulk Import' && <BulkImport />}
        {page === 'Cleanup' && <Cleanup />}
        {page === 'Settings' && <SettingsPage />}
      </main>
    </div>
  );
}
