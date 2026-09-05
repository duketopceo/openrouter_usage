// ui.js — shared formatting helpers for this plugin's Alpine stores.
export function fmtUsd(value) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const a = Math.abs(n);
  if (a > 0 && a < 0.01) return `$${n.toFixed(4)}`;
  if (a < 1) return `$${n.toFixed(3)}`;
  return `$${n.toFixed(2)}`;
}

export function fmtNum(value, digits = 0) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

export function fmtMs(value) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n >= 1000 ? `${(n / 1000).toFixed(2)}s` : `${Math.round(n)}ms`;
}

export function pctChange(cur, prev) {
  const c = Number(cur);
  const p = Number(prev);
  if (!Number.isFinite(c) || !Number.isFinite(p) || p === 0) return null;
  return ((c - p) / p) * 100;
}

export function barPct(value, max) {
  const v = Number(value);
  const m = Number(max);
  if (!Number.isFinite(v) || !Number.isFinite(m) || v <= 0 || m <= 0) return "0%";
  return `${Math.min(100, Math.max(2, (v / m) * 100))}%`;
}

export function maxOf(items, pick) {
  const nums = (items || []).map((i) => {
    const v = typeof pick === "function" ? pick(i) : i?.[pick];
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  });
  return Math.max(0.0001, ...nums);
}

export function relTime(iso) {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return String(iso);
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleString();
}

// Parse "M/D" or ISO-ish labels into a UTC y/m/d key for robust comparisons.
export function dayKey(label, year) {
  if (!label) return null;
  const m = String(label).match(/^(\d{1,2})\/(\d{1,2})$/);
  if (m) return { y: year ?? new Date().getUTCFullYear(), m: +m[1], d: +m[2] };
  const d = new Date(label);
  if (!Number.isFinite(d.getTime())) return null;
  return { y: d.getUTCFullYear(), m: d.getUTCMonth() + 1, d: d.getUTCDate() };
}
