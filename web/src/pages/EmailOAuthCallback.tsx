// Google sends the mailbox owner back here after they approve Gmail access.
// We hand the one-time code to the API, which verifies it and stores the grant.
import { useEffect, useRef, useState, type ReactElement } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api';
import { Spinner } from '../components/ui';
import { errMessage, useToast } from '../components/toast';

interface Connected { address: string }

export default function EmailOAuthCallback(): ReactElement {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return; // the code is single-use: never submit it twice
    ran.current = true;

    const denied = params.get('error');
    const code = params.get('code');
    const state = params.get('state');
    if (denied) {
      setError(denied === 'access_denied' ? 'Access was not approved, so nothing was connected.' : `Google returned: ${denied}`);
      return;
    }
    if (!code || !state) {
      setError('This page needs to be opened by Google after you approve access. Start from the Email page.');
      return;
    }
    api
      .post<Connected>('/v1/email-sync/oauth/callback', { code, state })
      .then((mb) => {
        toast.success(`${mb.address} connected`);
        navigate('/email', { replace: true });
      })
      .catch((e: unknown) => setError(errMessage(e, 'Could not connect the mailbox.')));
  }, [params, navigate, toast]);

  if (error) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center p-4">
        <div className="card-glow w-full max-w-md text-center">
          <span className="eyebrow">Gmail connection</span>
          <h1 className="mt-2 text-xl">Mailbox not connected</h1>
          <p className="mt-2 text-sm text-flamingo">{error}</p>
          <Link to="/email" className="btn-primary mt-6 inline-flex">Back to Email</Link>
        </div>
      </div>
    );
  }
  return <Spinner label="Connecting mailbox…" />;
}
