import { type ReactElement, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { handleCallback } from '../auth';
import { Spinner } from '../components/ui';

export default function Callback(): ReactElement {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const errParam = params.get('error');
    const errDesc = params.get('error_description');
    if (errParam) {
      setError(errDesc ? `${errParam}: ${errDesc}` : errParam);
      return;
    }

    const code = params.get('code');
    if (!code) {
      setError('No authorization code was returned. Please try signing in again.');
      return;
    }

    handleCallback(code)
      .then(() => navigate('/', { replace: true }))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : 'Failed to complete sign-in.'),
      );
  }, [params, navigate]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="card-glow w-full max-w-md text-center">
          <span className="eyebrow">Sign-in error</span>
          <h1 className="mt-2 text-xl">We couldn't sign you in</h1>
          <p className="mt-2 text-sm text-flamingo">{error}</p>
          <Link to="/login" className="btn-primary mt-6 inline-flex">
            Back to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="card-glow flex w-full max-w-md flex-col items-center gap-3 text-center">
        <img src="/brand/tensorbay-logo-dark.webp" alt="TensorBay" className="h-9" />
        <Spinner label="Completing sign-in…" />
      </div>
    </div>
  );
}
