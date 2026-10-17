import { type ReactElement, useMemo, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { decodeClaims, getSession, logout, type UserClaims } from '../auth';

interface NavItem {
  to: string;
  label: string;
  role?: string; // if set, only shown to users in this Cognito group
}

const NAV: NavItem[] = [
  { to: '/', label: 'Dashboard' },
  { to: '/customers', label: 'Customers' },
  { to: '/sales', label: 'Sales Pipeline' },
  { to: '/catalog', label: 'Catalog & Pricing' },
  { to: '/contracts', label: 'Contracts' },
  { to: '/inventory', label: 'Inventory' },
  { to: '/capacity', label: 'Capacity' },
  { to: '/reservations', label: 'Reservations' },
  { to: '/documents', label: 'AI Documents' },
  { to: '/admin', label: 'Admin', role: 'SUPER_ADMIN' },
];

function useClaims(): UserClaims | null {
  return useMemo(() => {
    const session = getSession();
    if (!session?.idToken) return null;
    try {
      return decodeClaims(session.idToken);
    } catch {
      return null;
    }
  }, []);
}

function navClass({ isActive }: { isActive: boolean }): string {
  const base =
    'flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition';
  return isActive
    ? `${base} bg-cyan/10 text-cyan shadow-glow`
    : `${base} text-grape-soft hover:bg-white/5 hover:text-white`;
}

export function AppLayout(): ReactElement {
  const claims = useClaims();
  const [mobileOpen, setMobileOpen] = useState(false);

  const displayName = claims?.name ?? claims?.email ?? 'Signed in';
  const displayEmail = claims?.email ?? '';

  const sidebar = (
    <div className="flex h-full flex-col gap-6 p-4">
      <NavLink to="/" className="flex items-center gap-3 px-1.5" onClick={() => setMobileOpen(false)}>
        <img
          src="/brand/tensorbay-symbol.webp"
          alt="TensorBay"
          className="h-9 w-9 rounded-lg"
        />
        <div className="leading-tight">
          <div className="text-sm font-bold text-white">TensorBay</div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-grape-soft">
            Control Plane
          </div>
        </div>
      </NavLink>

      <nav className="flex flex-1 flex-col gap-1">
        {NAV.filter(
          (item) => !item.role || (claims?.groups ?? []).includes(item.role),
        ).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={navClass}
            onClick={() => setMobileOpen(false)}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/5 pt-4 text-[11px] text-grape-soft/70">
        TensorBay · GPU Control Plane
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 border-r border-white/5 bg-space-700/40 md:block">
        {sidebar}
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-space-900/70 backdrop-blur-sm md:hidden"
          onClick={() => setMobileOpen(false)}
          role="presentation"
        >
          <aside
            className="h-full w-64 border-r border-white/5 bg-space-700"
            onClick={(e) => e.stopPropagation()}
          >
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Topbar */}
        <header className="sticky top-0 z-30 flex items-center justify-between gap-4 border-b border-white/5 bg-space-900/80 px-4 py-3 backdrop-blur-md md:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-lg border border-white/10 px-2.5 py-1.5 text-grape-soft transition hover:text-white md:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
            >
              ☰
            </button>
            <img
              src="/brand/tensorbay-logo-dark.webp"
              alt="TensorBay"
              className="h-7 md:hidden"
            />
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <div className="text-sm font-medium text-white">{displayName}</div>
              {displayEmail && (
                <div className="text-xs text-grape-soft">{displayEmail}</div>
              )}
            </div>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-gradient text-sm font-bold text-space-900">
              {(displayEmail || displayName).slice(0, 1).toUpperCase()}
            </div>
            <button type="button" className="btn-ghost" onClick={() => logout()}>
              Logout
            </button>
          </div>
        </header>

        <main className="flex-1 px-4 py-6 md:px-6 md:py-8">
          <div className="mx-auto w-full max-w-7xl">
            <Outlet />
          </div>
        </main>

        <footer className="border-t border-white/5 px-4 py-4 text-center text-xs text-grape-soft/70 md:px-6">
          NeoCloud · TensorBay GPU Control Plane
        </footer>
      </div>
    </div>
  );
}

export default AppLayout;
