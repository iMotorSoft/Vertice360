export const WORKFLOW_ID = "vertice360-ai-workflow";

export const RUN_STATUS_LABELS = {
  RUNNING: "Running",
  COMPLETED: "Completed",
  FAILED: "Failed",
};

export const RUN_STATUS_TONES = {
  RUNNING: "badge-info",
  COMPLETED: "badge-success",
  FAILED: "badge-error",
};

export const statusLabel = (status) => RUN_STATUS_LABELS[status] || status || "Unknown";
export const statusTone = (status) => RUN_STATUS_TONES[status] || "badge-ghost";

export const formatTime = (timestamp) => {
  if (!timestamp) return "--:--:--";
  return new Date(timestamp).toLocaleTimeString("en-GB", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};

export const formatDate = (timestamp) => {
  if (!timestamp) return "--";
  return new Date(timestamp).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
  });
};

export const shortId = (value) => {
  if (!value) return "--";
  const text = String(value);
  if (text.length <= 10) return text;
  return `${text.slice(0, 6)}...${text.slice(-3)}`;
};

export const normalizePayload = (evt) => {
  if (!evt) return {};
  return evt.value ?? evt.data ?? evt.payload ?? evt;
};

export const normalizeSseEvent = (raw) => {
  if (!raw) return null;
  let type = raw.event ?? raw.type ?? raw.name ?? raw.eventName;
  if (type === "CUSTOM" && raw.name) {
    type = raw.name;
  }
  const value = raw.value ?? raw.data ?? raw.payload ?? raw;
  const ts = raw.timestamp ?? raw.ts ?? Date.now();
  return { type, ts, value, raw };
};
