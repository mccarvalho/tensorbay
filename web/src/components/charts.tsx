// Brand-themed chart primitives on top of recharts, matching the TensorBay
// palette (space #0D0221, cyan #00D4FF, grape #B165FB, flamingo #FF6EC4,
// grape-soft #B9A9D6). Keeps chart styling consistent across the app.
import type { ReactElement, ReactNode } from 'react';
import { ResponsiveContainer, Tooltip, type TooltipProps } from 'recharts';

export const CHART = {
  cyan: '#00D4FF',
  grape: '#B165FB',
  flamingo: '#FF6EC4',
  grapeSoft: '#B9A9D6',
  white: '#E9E6F5',
  offline: 'rgba(255,255,255,0.18)',
  maintenance: '#7C5CBF',
  grid: 'rgba(255,255,255,0.08)',
  axis: '#B9A9D6',
} as const;

// Ordered palette for categorical series.
export const SERIES_COLORS = [CHART.cyan, CHART.grape, CHART.flamingo, CHART.grapeSoft, CHART.maintenance, CHART.offline];

/** Dark, on-brand tooltip. */
export function BrandTooltip({ active, payload, label, valueFormatter }: TooltipProps<number, string> & {
  valueFormatter?: (v: number, name: string) => string;
}): ReactElement | null {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-lg border border-white/10 bg-space-700/95 px-3 py-2 text-xs shadow-card backdrop-blur">
      {label != null && <div className="mb-1 font-semibold text-white">{label}</div>}
      <div className="flex flex-col gap-0.5">
        {payload.map((p, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: (p.color as string) ?? CHART.cyan }} />
            <span className="text-grape-soft">{p.name}</span>
            <span className="ml-auto font-medium text-white">
              {valueFormatter ? valueFormatter(Number(p.value), String(p.name)) : Number(p.value).toLocaleString('en-US')}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ThemedTooltip(props: { valueFormatter?: (v: number, name: string) => string }): ReactElement {
  return (
    <Tooltip
      cursor={{ fill: 'rgba(255,255,255,0.04)' }}
      content={<BrandTooltip valueFormatter={props.valueFormatter} />}
    />
  );
}

/** Card frame + title for a chart, with a fixed responsive height. */
export function ChartCard({ title, hint, height = 280, children }: {
  title: string; hint?: string; height?: number; children: ReactNode;
}): ReactElement {
  return (
    <div className="card flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        {hint && <span className="text-xs text-grape-soft">{hint}</span>}
      </div>
      <div style={{ width: '100%', height }}>
        <ResponsiveContainer width="100%" height="100%">
          {children as ReactElement}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
