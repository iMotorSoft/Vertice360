const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

export const formatDurationShort = (ms) => {
  const abs = Math.abs(ms);
  if (!Number.isFinite(abs)) return "-";
  const seconds = Math.floor(abs / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
};

export const formatRelative = (ts, now = Date.now()) => {
  if (!ts) return "-";
  const diff = now - ts;
  const label = formatDurationShort(diff);
  if (label === "0s") return "justo ahora";
  return diff >= 0 ? `hace ${label}` : `en ${label}`;
};

export const formatClock = (ts) => {
  if (!ts) return "-";
  const date = new Date(ts);
  return date.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
};

export const formatDate = (ts) => {
  if (!ts) return "-";
  return new Date(ts).toLocaleDateString("es-AR", { day: "2-digit", month: "short" });
};

export const formatCountdown = (dueAt, now = Date.now(), breachedAt = null) => {
  if (!dueAt) return "Sin SLA";
  const diff = dueAt - now;
  if (breachedAt || diff <= 0) {
    return `Breached ${formatDurationShort(diff)}`;
  }
  return `${formatDurationShort(diff)} restantes`;
};

export const progressFromWindow = (startAt, dueAt, now = Date.now()) => {
  if (!startAt || !dueAt || dueAt <= startAt) return 0;
  const total = dueAt - startAt;
  const elapsed = now - startAt;
  return clamp(Math.round((elapsed / total) * 100), 0, 100);
};
