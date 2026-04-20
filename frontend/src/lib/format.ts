/**
 * Shared timestamp and value formatters.
 * §4.5 — All pages use these for consistent tabular-nums display.
 */

/** HH:MM:SS or HH:MM:SS.f — matches design spec tabular-nums pattern */
export function formatTimestamp(ts: number, opts?: { fractional?: boolean }): string {
  const d = new Date(ts);
  if (opts?.fractional) {
    return d.toLocaleTimeString([], { hour12: false, fractionalSecondDigits: 1 });
  }
  return d.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/** HH:MM:SS.mmm — events page precision format */
export function formatTimestampPrecise(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour12: false }) + '.' + String(d.getMilliseconds()).padStart(3, '0');
}

/** Full locale string for detail panels */
export function formatFull(iso: string): string {
  return new Date(iso).toLocaleString();
}

/** Relative age: "5m ago", "3h ago", "2d ago", or date */
export function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 0) return 'just now';
  if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  if (diff < 86400000 * 30) return `${Math.floor(diff / 86400000)}d ago`;
  return new Date(iso).toLocaleDateString();
}

/** Duration: "234ms" or "1.23s" */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

/** Cost: "$0.0234" or "<$0.0001" */
export function formatCost(cost: number): string {
  if (cost < 0.0001) return '<$0.0001';
  return `$${cost.toFixed(4)}`;
}

/** Format Unix-seconds timestamp as HH:MM */
export function formatTimestampSecs(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/** Relative age from Unix-seconds timestamp */
export function formatRelativeSecs(ts: number): string {
  return formatRelative(new Date(ts * 1000).toISOString());
}

/** Duration in seconds: "42m 17s" */
export function formatDurationSecs(s: number): string {
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}