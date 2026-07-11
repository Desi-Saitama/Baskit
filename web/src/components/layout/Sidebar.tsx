import { useState } from 'react';
import {
  LayoutDashboard, BarChart3, Sparkles, FileUp,
  Archive, Wand2, Settings, X, Menu, ReceiptText,
} from 'lucide-react';

const navItems = [
  { key: 'Dashboard', icon: LayoutDashboard },
  { key: 'Apps & Items', icon: BarChart3 },
  { key: 'History', icon: ReceiptText },
  { key: 'Savings', icon: Sparkles },
  { key: 'Upload', icon: FileUp },
  { key: 'Bulk Import', icon: Archive },
  { key: 'Cleanup', icon: Wand2 },
  { key: 'Settings', icon: Settings },
];

interface SidebarProps {
  page: string;
  onNavigate: (page: string) => void;
}

export default function Sidebar({ page, onNavigate }: SidebarProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setOpen(true)}
        className="fixed top-4 left-4 z-40 rounded-xl bg-white/60 p-3 backdrop-blur-sm lg:hidden"
        aria-label="Open menu"
      >
        <Menu className="size-5 text-stone-700" />
      </button>

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/20 backdrop-blur-sm lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-72 border-r p-4 backdrop-blur-2xl transition-transform duration-300 lg:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{
          borderColor: 'var(--sidebar-border)',
          backgroundColor: 'var(--sidebar)',
        }}
      >
        {/* Logo */}
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img
              src="/baskit-logo.png"
              alt="Baskit logo"
              className="size-11 rounded-2xl object-cover shadow-lg shadow-orange-300/30"
            />
            <div>
              <b className="text-lg text-stone-900">Baskit</b>
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-stone-500">
                receipt ai
              </p>
            </div>
          </div>
          <button
            className="rounded-lg p-2 hover:bg-orange-50 lg:hidden"
            onClick={() => setOpen(false)}
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Nav items */}
        <nav className="space-y-1.5">
          {navItems.map(({ key, icon: Icon }) => {
            const active = page === key;
            return (
              <button
                key={key}
                onClick={() => {
                  onNavigate(key);
                  setOpen(false);
                }}
                className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left text-sm font-semibold transition-all duration-200 ${
                  active
                    ? 'bg-[var(--sidebar-accent)] text-orange-900 shadow-inner'
                    : 'text-stone-700 hover:bg-orange-50/80 hover:text-stone-950'
                }`}
              >
                <Icon className="size-[18px]" />
                <span>{key}</span>
              </button>
            );
          })}
        </nav>

        {/* Gemini parser status */}
        <div className="glass-card mt-8 bg-gradient-to-br from-orange-200/70 to-amber-100/70">
          <p className="text-sm font-semibold text-stone-800">Gemini parser</p>
          <p className="mt-1 text-xs text-stone-500">
            4-key rotation active. Ready to parse.
          </p>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/60">
            <div className="h-full w-3/4 rounded-full bg-orange-500 transition-all duration-1000" />
          </div>
        </div>
      </aside>
    </>
  );
}
