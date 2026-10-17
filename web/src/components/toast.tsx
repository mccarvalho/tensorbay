// Lightweight toast system — success/error/info notifications on mutations.
// Mount <ToastProvider> near the app root; call useToast() anywhere to push.
import {
  createContext, useCallback, useContext, useRef, useState, type ReactNode, type ReactElement,
} from 'react';

type ToastKind = 'success' | 'error' | 'info';
interface Toast { id: number; kind: ToastKind; message: string }

interface ToastApi {
  toast: (message: string, kind?: ToastKind) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const KIND_STYLES: Record<ToastKind, string> = {
  success: 'border-cyan/40 bg-space-700/95 text-white',
  error: 'border-flamingo/50 bg-space-700/95 text-white',
  info: 'border-grape/40 bg-space-700/95 text-white',
};
const KIND_DOT: Record<ToastKind, string> = {
  success: 'bg-cyan',
  error: 'bg-flamingo',
  info: 'bg-grape',
};

export function ToastProvider({ children }: { children: ReactNode }): ReactElement {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback((message: string, kind: ToastKind = 'info') => {
    const id = nextId.current++;
    setToasts((prev) => [...prev, { id, kind, message }]);
    // Errors linger longer so they can be read.
    const ttl = kind === 'error' ? 6000 : 3500;
    setTimeout(() => remove(id), ttl);
  }, [remove]);

  const api: ToastApi = {
    toast: push,
    success: (m) => push(m, 'success'),
    error: (m) => push(m, 'error'),
    info: (m) => push(m, 'info'),
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id}
            role="status"
            className={`pointer-events-auto flex items-start gap-2.5 rounded-xl border px-3.5 py-2.5 text-sm shadow-card backdrop-blur ${KIND_STYLES[t.kind]}`}>
            <span className={`mt-1 inline-block h-2 w-2 shrink-0 rounded-full ${KIND_DOT[t.kind]}`} />
            <span className="flex-1">{t.message}</span>
            <button type="button" aria-label="Dismiss"
              className="shrink-0 text-grape-soft transition hover:text-white"
              onClick={() => remove(t.id)}>✕</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // Fail safe: no provider -> no-op (keeps pages usable in isolation/tests).
    return { toast: () => {}, success: () => {}, error: () => {}, info: () => {} };
  }
  return ctx;
}

/** Best-effort message extraction from an unknown error (ApiError, Error, etc). */
export function errMessage(e: unknown, fallback = 'Something went wrong'): string {
  if (e && typeof e === 'object' && 'message' in e && typeof (e as { message: unknown }).message === 'string') {
    return (e as { message: string }).message;
  }
  return fallback;
}
