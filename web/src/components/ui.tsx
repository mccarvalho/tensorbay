// Shared presentational primitives for the NeoCloud control plane.
// Styled to match the TensorBay Commission Plan deck (deep-purple dark theme,
// cyan eyebrows, big-number KPI cards, purple->cyan gradient accents).
import {
  type ReactNode,
  type ReactElement,
  useEffect,
} from 'react';
import { ApiError } from '../api';

// ---------------------------------------------------------------------------
// KpiCard — big-number metric tile
// ---------------------------------------------------------------------------
export interface KpiCardProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: 'cyan' | 'grape' | 'flamingo' | 'white';
}

const ACCENT_TEXT: Record<NonNullable<KpiCardProps['accent']>, string> = {
  cyan: 'text-cyan',
  grape: 'text-grape',
  flamingo: 'text-flamingo',
  white: 'text-white',
};

export function KpiCard({ label, value, sub, accent = 'white' }: KpiCardProps): ReactElement {
  return (
    <div className="card-glow flex flex-col gap-1">
      <span className="label">{label}</span>
      <span className={`text-3xl font-extrabold tracking-tight md:text-4xl ${ACCENT_TEXT[accent]}`}>
        {value}
      </span>
      {sub !== undefined && sub !== null && (
        <span className="text-sm text-grape-soft/80">{sub}</span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SectionHeader — cyan eyebrow + title + optional description
// ---------------------------------------------------------------------------
export interface SectionHeaderProps {
  eyebrow: string;
  title: string;
  description?: ReactNode;
}

export function SectionHeader({ eyebrow, title, description }: SectionHeaderProps): ReactElement {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="eyebrow">{eyebrow}</span>
      <h1 className="text-2xl md:text-3xl">{title}</h1>
      {description && <p className="max-w-2xl text-sm text-grape-soft">{description}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Spinner — branded loading indicator
// ---------------------------------------------------------------------------
export interface SpinnerProps {
  label?: string;
  className?: string;
}

export function Spinner({ label, className }: SpinnerProps): ReactElement {
  return (
    <div className={`flex items-center justify-center gap-3 py-10 ${className ?? ''}`}>
      <span
        className="h-6 w-6 animate-spin rounded-full border-2 border-cyan/30 border-t-cyan"
        aria-hidden="true"
      />
      {label && <span className="text-sm text-grape-soft">{label}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// EmptyState
// ---------------------------------------------------------------------------
export interface EmptyStateProps {
  title: string;
  hint?: string;
}

export function EmptyState({ title, hint }: EmptyStateProps): ReactElement {
  return (
    <div className="card flex flex-col items-center gap-2 py-12 text-center">
      <div className="h-10 w-10 rounded-xl bg-brand-gradient opacity-70" aria-hidden="true" />
      <h3 className="text-lg">{title}</h3>
      {hint && <p className="max-w-md text-sm text-grape-soft">{hint}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ErrorState
// ---------------------------------------------------------------------------
export interface ErrorStateProps {
  error: unknown;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.status} · ${error.message}`;
  }
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'An unexpected error occurred.';
}

export function ErrorState({ error }: ErrorStateProps): ReactElement {
  return (
    <div className="card flex flex-col items-center gap-2 border-flamingo/30 py-10 text-center">
      <div className="h-10 w-10 rounded-xl bg-flamingo/20" aria-hidden="true" />
      <h3 className="text-lg text-white">Something went wrong</h3>
      <p className="max-w-md text-sm text-flamingo">{errorMessage(error)}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------
export type BadgeTone = 'cyan' | 'grape' | 'flamingo' | 'neutral' | 'success' | 'warning';

export interface BadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
}

const BADGE_TONE: Record<BadgeTone, string> = {
  cyan: 'bg-cyan/15 text-cyan',
  grape: 'bg-grape/15 text-grape',
  flamingo: 'bg-flamingo/15 text-flamingo',
  neutral: 'bg-white/10 text-grape-soft',
  success: 'bg-emerald-400/15 text-emerald-300',
  warning: 'bg-amber-400/15 text-amber-300',
};

export function Badge({ children, tone = 'neutral' }: BadgeProps): ReactElement {
  return <span className={`badge ${BADGE_TONE[tone]}`}>{children}</span>;
}

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------
export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}

export function Modal({ open, onClose, title, children }: ModalProps): ReactElement | null {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-space-900/70 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="card-glow w-full max-w-lg"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl">{title}</h2>
          <button
            type="button"
            className="rounded-lg px-2 py-1 text-grape-soft transition hover:bg-white/5 hover:text-white"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DataTable — generic table
// ---------------------------------------------------------------------------
export interface Column<Row> {
  key: string;
  header: ReactNode;
  render?: (row: Row) => ReactNode;
  className?: string;
}

export interface DataTableProps<Row> {
  columns: Array<Column<Row>>;
  rows: Row[];
  rowKey?: (row: Row, index: number) => string | number;
  empty?: ReactNode;
}

function defaultCell<Row>(row: Row, key: string): ReactNode {
  const value = (row as Record<string, unknown>)[key];
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  empty,
}: DataTableProps<Row>): ReactElement {
  if (rows.length === 0) {
    return (
      <>{empty ?? <EmptyState title="No records" hint="Nothing to show yet." />}</>
    );
  }
  return (
    <div className="table-wrap overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} className={`th ${col.className ?? ''}`}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={rowKey ? rowKey(row, i) : i} className="transition hover:bg-white/5">
              {columns.map((col) => (
                <td key={col.key} className={`td ${col.className ?? ''}`}>
                  {col.render ? col.render(row) : defaultCell(row, col.key)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
