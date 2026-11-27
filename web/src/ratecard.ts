// TensorBay rate card: list price per GPU-hour by platform, term and upfront share (orders of 32+ servers).
export interface RateRow { id: string; platform: string; term_months: number; upfront_pct: string | number; price_per_gpu_hour: string | number }

export const GPUS_PER_SERVER = 8;
export const MIN_ORDER_SERVERS = 32;
export const MIN_ORDER_GPUS = GPUS_PER_SERVER * MIN_ORDER_SERVERS;
export const HOURS_PER_MONTH = 730;

/** Rate card platform of a GPU model name ("HGX B300 liquid-cooled" -> "B300"); null = no list price. */
export function platformKey(gpuModel: string): string | null {
  const m = gpuModel.toUpperCase().replace(/[\s_-]/g, '');
  if (m.includes('GB300')) return 'GB300';
  if (m.includes('VR200') || m.includes('VERARUBIN')) return 'VR200';
  if (m.includes('B300')) return 'B300';
  if (m.includes('B200')) return 'B200';
  return null;
}

export function findRate(rates: RateRow[], gpuModel: string, term: number, upfront: number | null): RateRow | null {
  const key = platformKey(gpuModel);
  if (!key || upfront == null) return null;
  return rates.find((r) => r.platform === key && r.term_months === term && Number(r.upfront_pct) === upfront) ?? null;
}

/** "36 or 60 months with 35% / 65% upfront" for the platform, to tell the user what the card offers. */
export function rateOptions(rates: RateRow[], gpuModel: string): string | null {
  const key = platformKey(gpuModel);
  const rows = rates.filter((r) => r.platform === key);
  if (!rows.length) return null;
  const terms = [...new Set(rows.map((r) => r.term_months))].sort((a, b) => a - b);
  const ups = [...new Set(rows.map((r) => Number(r.upfront_pct)))].sort((a, b) => a - b);
  return `${terms.join(' or ')} months with ${ups.map((u) => `${u}%`).join(' / ')} upfront`;
}
