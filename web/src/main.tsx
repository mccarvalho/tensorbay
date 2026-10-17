import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import './index.css';
import { ApiError } from './api';

// Kill any stale service worker from a previous deploy and clear its caches.
// A leftover SW can intercept /v1/* calls and return the cached SPA shell
// (index.html), which surfaces as "Unexpected token '<' ... is not valid JSON".
if ('serviceWorker' in navigator) {
  navigator.serviceWorker
    .getRegistrations()
    .then((regs) => regs.forEach((r) => void r.unregister()))
    .catch(() => undefined);
  if (window.caches) {
    caches
      .keys()
      .then((keys) => keys.forEach((k) => void caches.delete(k)))
      .catch(() => undefined);
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // Never retry auth/permission failures — avoids a 401→refresh→401 storm.
      retry: (failureCount, error) => {
        if (error instanceof ApiError && [401, 403, 404, 422].includes(error.status)) {
          return false;
        }
        return failureCount < 1;
      },
    },
  },
});

const rootEl = document.getElementById('root');
if (!rootEl) throw new Error('Root element #root not found');

createRoot(rootEl).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
