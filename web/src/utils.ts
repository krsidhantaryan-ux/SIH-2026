export function formatUtc(value: string, includeYear = false): string {
  return `${new Date(value).toLocaleString("en-GB", {
    timeZone: "UTC",
    day: "2-digit",
    month: "short",
    year: includeYear ? "numeric" : undefined,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })} UTC`;
}

export function signed(value: number | null, suffix = ""): string {
  if (value === null) return "Insufficient history";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(0)}${suffix}`;
}

export function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function bytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
