// TensorBay's date standard is MM/DD/YYYY, everywhere. The API keeps ISO (YYYY-MM-DD);
// these helpers convert at the edge so no screen depends on the browser's language.

const pad = (n: number): string => String(n).padStart(2, '0');

/** "2027-01-30" (or a full ISO timestamp) -> "01/30/2027". Anything unreadable -> ''. */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[2]}/${m[3]}/${m[1]}` : '';
}

/** A timestamp in the user's time zone: "01/30/2027, 9:30 AM". */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const h = d.getHours() % 12 || 12;
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())}/${d.getFullYear()}, ${h}:${pad(d.getMinutes())} ${d.getHours() < 12 ? 'AM' : 'PM'}`;
}

/** A typed "01/30/2027" -> "2027-01-30"; null if it is not a real calendar date. */
export function parseDate(text: string): string | null {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(text.trim());
  if (!m) return null;
  const [mm, dd, yyyy] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const d = new Date(Date.UTC(yyyy, mm - 1, dd));
  if (d.getUTCFullYear() !== yyyy || d.getUTCMonth() !== mm - 1 || d.getUTCDate() !== dd) return null;
  return `${yyyy}-${pad(mm)}-${pad(dd)}`;
}

/** While typing: digits only, slashes inserted as MM/DD/YYYY. */
export function maskDate(text: string): string {
  const digits = text.replace(/\D/g, '').slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}
