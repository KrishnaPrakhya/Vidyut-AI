export function formatNumber(val?: number | null, digits = 1): string {
  if (val === undefined || val === null || !Number.isFinite(val)) return "—";
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(val);
}

export function formatLabel(val: string): string {
  return val.replaceAll("_", " ").replace(/\b\w/g, (l) => l.toUpperCase());
}
