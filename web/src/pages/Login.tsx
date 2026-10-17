import { type ReactElement, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { isAuthenticated, login } from '../auth';

export default function Login(): ReactElement {
  const [busy, setBusy] = useState<'google' | 'email' | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (isAuthenticated()) {
    return <Navigate to="/" replace />;
  }

  async function start(useGoogle: boolean): Promise<void> {
    setError(null);
    setBusy(useGoogle ? 'google' : 'email');
    try {
      await login(useGoogle ? { useGoogle: true } : undefined);
    } catch (e) {
      setBusy(null);
      setError(e instanceof Error ? e.message : 'Unable to start sign-in.');
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="card-glow w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-4 text-center">
          <img
            src="/brand/tensorbay-logo-dark.webp"
            alt="TensorBay"
            className="h-10"
          />
          <div>
            <span className="eyebrow">GPU Control Plane</span>
            <h1 className="mt-2 text-2xl">Welcome to NeoCloud</h1>
            <p className="mt-1 text-sm text-grape-soft">
              Sign in to manage the commercial, capacity, and financial lifecycle
              of your GPU infrastructure.
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-flamingo/30 bg-flamingo/10 px-3.5 py-2.5 text-sm text-flamingo">
            {error}
          </div>
        )}

        <div className="flex flex-col gap-3">
          <button
            type="button"
            className="btn-primary w-full"
            disabled={busy !== null}
            onClick={() => void start(true)}
          >
            {busy === 'google' ? 'Redirecting…' : 'Sign in with Google'}
          </button>
          <button
            type="button"
            className="btn-ghost w-full"
            disabled={busy !== null}
            onClick={() => void start(false)}
          >
            {busy === 'email' ? 'Redirecting…' : 'Sign in with email'}
          </button>
        </div>

        <p className="mt-8 text-center text-xs text-grape-soft/70">
          NeoCloud · TensorBay GPU Control Plane
        </p>
      </div>
    </div>
  );
}
