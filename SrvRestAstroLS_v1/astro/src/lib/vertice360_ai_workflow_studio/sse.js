import { URL_SSE } from "../../components/global.js";
import { normalizeSseEvent } from "./types";

const EVENT_TYPES = [
  "ai_workflow.run.started",
  "ai_workflow.run.step",
  "ai_workflow.run.completed",
  "ai_workflow.run.failed",
  "messaging.inbound",
  "messaging.inbound.raw",
  "messaging.outbound",
  "messaging.status",
  "human.action_required",
];

let source = null;
let reconnectTimer = null;
let reconnectAttempt = 0;
let isUnloading = false;
let debugLogged = false;

const DEBUG_SSE =
  typeof window !== "undefined" && window?.localStorage?.getItem("VERTICE360_SSE_DEBUG") === "1";

const backoffDelay = () => {
  const base = 500;
  const delay = base * Math.pow(2, reconnectAttempt);
  return Math.min(delay, 5000);
};

if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    isUnloading = true;
    disconnectSse();
  });
}

const attachHandlers = (handlers) => {
  if (!source) return;
  const onEvent = typeof handlers.onEvent === "function" ? handlers.onEvent : null;
  const onMeta = typeof handlers.onMeta === "function" ? handlers.onMeta : null;
  const onStatus = typeof handlers.onStatus === "function" ? handlers.onStatus : null;

  const handle = (event) => {
    let raw = null;
    try {
      raw = JSON.parse(event.data);
    } catch (err) {
      raw = { data: event.data };
    }

    const parsed = normalizeSseEvent(raw);
    if (!parsed) return;

    if (DEBUG_SSE && !debugLogged) {
      debugLogged = true;
      console.info("SSE normalized event", parsed);
    }
    onMeta?.(parsed);
    onEvent?.(parsed);
  };

  // We listen to "message" for generic SSE, or specific event types if backend sends them as named events
  // But typically in this setup we might just listen to everything if they come as named events.
  // The backend says "Backend emite SSE en el stream global URL_SSE, eventos: ai_workflow.*"
  // So we probably need to listen to specific event names if they are emitted as such.
  EVENT_TYPES.forEach((evt) => source.addEventListener(evt, handle));

  // Also listen to generic messages just in case
  source.onmessage = handle;

  source.onopen = () => {
    reconnectAttempt = 0;
    onStatus?.("connected");
  };

  source.onerror = () => {
    if (isUnloading) return;
    onStatus?.("disconnected");
    if (source) {
      source.close();
      source = null;
    }
    if (reconnectTimer) return;
    const delay = backoffDelay();
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      reconnectAttempt += 1;
      connectSse(handlers);
    }, delay);
  };
};

export const connectSse = (handlers = {}) => {
  if (typeof window === "undefined") return () => { };
  if (isUnloading) return () => { };

  if (source && (source.readyState === EventSource.OPEN || source.readyState === EventSource.CONNECTING)) {
    return () => { };
  }

  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  try {
    source = new EventSource(URL_SSE);
    attachHandlers(handlers);
  } catch (err) {
    handlers.onStatus?.("disconnected");
  }

  return () => disconnectSse();
};

export const disconnectSse = () => {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (source) {
    source.close();
    source = null;
  }
};
