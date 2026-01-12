import { URL_SSE } from "../../components/global";

const EVENT_TYPES = [
  "ticket.created",
  "ticket.updated",
  "ticket.assigned",
  "ticket.sla.started",
  "ticket.sla.breached",
  "ticket.escalated",
  "ticket.closed",
  "ticket.survey.sent",
  "ticket.survey.received",
  "messaging.inbound",
  "messaging.inbound.raw",
  "messaging.outbound",
  "messaging.delivery",
  "workflow.reset",
  "workflow.error",
];

let source = null;
let reconnectTimer = null;
let reconnectAttempt = 0;
let isUnloading = false;

const backoffDelay = () => {
  const base = 500;
  const delay = base * Math.pow(2, reconnectAttempt);
  return Math.min(delay, 5000);
};

if (typeof window !== "undefined") {
  window.addEventListener("beforeunload", () => {
    isUnloading = true;
    disconnectWorkflowSSE();
  });
}

const parseEvent = (event) => {
  if (!event?.data) return null;
  try {
    const payload = JSON.parse(event.data);
    if (!payload || payload.type !== "CUSTOM") return null;
    return {
      name: payload.name,
      timestamp: payload.timestamp ?? payload.ts ?? Date.now(),
      correlationId: payload.correlationId ?? payload.ticketId ?? payload?.value?.ticketId,
      value: payload.value ?? {},
      raw: payload,
    };
  } catch (err) {
    return null;
  }
};

const attachHandlers = (handlers) => {
  if (!source) return;
  const onEvent = typeof handlers.onEvent === "function" ? handlers.onEvent : null;
  const onStatus = typeof handlers.onStatus === "function" ? handlers.onStatus : null;

  const handle = (event) => {
    const parsed = parseEvent(event);
    if (parsed) onEvent?.(parsed);
  };

  EVENT_TYPES.forEach((evt) => source.addEventListener(evt, handle));

  source.onopen = () => {
    reconnectAttempt = 0;
    onStatus?.(true);
  };

  source.onerror = () => {
    if (isUnloading) return;
    onStatus?.(false);
    if (source) {
      source.close();
      source = null;
    }
    if (reconnectTimer) return;
    const delay = backoffDelay();
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      reconnectAttempt += 1;
      connectWorkflowSSE(handlers);
    }, delay);
  };
};

export const connectWorkflowSSE = (handlers = {}) => {
  if (typeof window === "undefined") return () => {};
  if (isUnloading) return () => {};

  if (source && (source.readyState === EventSource.OPEN || source.readyState === EventSource.CONNECTING)) {
    return () => {};
  }

  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  try {
    source = new EventSource(URL_SSE);
    attachHandlers(handlers);
  } catch (err) {
    if (handlers.onStatus) handlers.onStatus(false);
  }

  return () => disconnectWorkflowSSE();
};

export const disconnectWorkflowSSE = () => {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (source) {
    source.close();
    source = null;
  }
};
