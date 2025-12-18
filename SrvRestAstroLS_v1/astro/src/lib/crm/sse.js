import { URL_SSE } from "../../components/global";
import { crm } from "./state.svelte";

const EVENT_TYPES = [
  "conversation.message.new",
  "conversation.message.status",
  "deal.stage.changed",
  "task.created",
  "task.completed",
];

// Single global EventSource to avoid duplicate SSE connections.
let es = null;
let reconnectTimer = null;
let isUnloading = false;

if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    isUnloading = true;
    disconnectCrmSSE();
  });
}

const setConnected = (connected) => {
  crm.setSseConnected?.(connected);
  if (connected) {
    console.log("[CRM SSE] Connected");
    crm.addToast?.("info", "SSE conectado");
  } else {
    // Suppress error toast if we are unloading the page
    if (!isUnloading) {
      crm.addToast?.("error", "Conexión SSE caída");
    }
  }
};

const handleMessage = (event) => {
  try {
    const parsed = JSON.parse(event.data);
    if (!parsed) return;

    if (parsed.type !== "CUSTOM") return;
    if (typeof parsed.name !== "string") return;
    if (!parsed.name.startsWith("conversation.") && !parsed.name.startsWith("deal.") && !parsed.name.startsWith("task.")) return;
    crm.handleSseEvent?.({ name: parsed.name, value: parsed.value, raw: parsed, event });
  } catch (err) {
    // Ignore heartbeat or non-json messages
  }
};

const attachHandlers = (source) => {
  EVENT_TYPES.forEach((evt) => source.addEventListener(evt, handleMessage));
  source.onmessage = handleMessage;

  source.onopen = () => setConnected(true);

  source.onerror = () => {
    if (isUnloading) return;
    setConnected(false);
    source.close();
    es = null;
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectCrmSSE();
    }, 1500);
  };
};

export const connectCrmSSE = () => {
  if (typeof window === "undefined") return;
  if (isUnloading) return;

  // Idempotency: if already connected/connecting, do nothing
  if (es && (es.readyState === EventSource.OPEN || es.readyState === EventSource.CONNECTING)) {
    return;
  }

  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (es) {
    es.close();
    es = null;
  }

  // Pure URL, no query params
  const url = URL_SSE;

  try {
    es = new EventSource(url);
    attachHandlers(es);
  } catch (err) {
    console.error("SSE connect error", err);
    es = null;
    setConnected(false);
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connectCrmSSE();
    }, 1500);
  }
};

export const disconnectCrmSSE = () => {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (es) {
    es.close();
    es = null;
  }
  setConnected(false);
};
