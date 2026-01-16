import * as api from "./api";
import { DEFAULT_REQUESTED_DOCS, isMessagingEvent, isTicketEvent } from "./types";

const MAX_TIMELINE = 200;
const MAX_LIVE_EVENTS = 300;
const DETAIL_TTL_MS = 10_000;

const toastId = () => crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);

const emptyTicket = (ticketId) => ({
  ticketId,
  status: "OPEN",
  channel: null,
  provider: null,
  customer: {},
  subject: "",
  assignee: null,
  requestedDocs: [],
  docsReceivedAt: null,
  sla: {},
  timeline: [],
  messages: [],
  createdAt: Date.now(),
  updatedAt: Date.now(),
  pulse: null,
});

const coerceTimestamp = (value) => {
  if (!value) return Date.now();
  if (typeof value === "number") return value;
  if (typeof value === "string" && value && !Number.isNaN(Number(value))) return Number(value);
  return Date.now();
};

const normalizeEvent = (evt) => {
  if (!evt) {
    return {
      id: `evt-${Math.random().toString(36).slice(2)}`,
      name: "CUSTOM",
      timestamp: Date.now(),
      correlationId: null,
      value: {},
      raw: null,
    };
  }
  const name = evt.name ?? evt?.raw?.name ?? "CUSTOM";
  const timestamp = coerceTimestamp(evt.timestamp ?? evt?.raw?.timestamp ?? evt?.raw?.ts);
  const value = evt.value ?? evt?.raw?.value ?? {};
  const correlationId = evt.correlationId ?? evt?.raw?.correlationId ?? value?.ticketId ?? null;
  return {
    id: `${name}-${timestamp}-${Math.random().toString(36).slice(2)}`,
    name,
    timestamp,
    correlationId,
    value,
    raw: evt.raw ?? evt,
  };
};

const getEventTicketId = (evt) => {
  const ticketId = evt?.value?.ticketId;
  if (typeof ticketId === "string" && ticketId.trim()) return ticketId;
  return null;
};

export function createWorkflowState() {
  let ticketsById = $state({});
  let ticketOrder = $state([]);
  let selectedTicketId = $state(null);
  let ticketsLoading = $state(true);
  let ticketsError = $state(null);
  let detailLoading = $state(false);
  let detailError = $state(null);
  let liveEvents = $state([]);
  let filters = $state({ text: "", type: "all", onlySelected: false });
  let search = $state("");
  let toasts = $state([]);
  let sse = $state({ connected: false, lastChangeMs: 0 });
  let lastEventByTicket = $state({});
  let lastFetchedByTicket = $state({});

  const timers = new Set();

  const addToast = (message, tone = "info") => {
    const id = toastId();
    toasts = [...toasts, { id, message, tone }];
    const timeoutId = setTimeout(() => {
      toasts = toasts.filter((toast) => toast.id !== id);
      timers.delete(timeoutId);
    }, 3600);
    timers.add(timeoutId);
  };

  const setSseConnected = (connected) => {
    sse = { connected, lastChangeMs: Date.now() };
  };

  const bumpTicketOrder = (ticketId) => {
    ticketOrder = [ticketId, ...ticketOrder.filter((id) => id !== ticketId)];
  };

  const mergeTicket = (base, patch) => {
    const next = { ...base, ...patch };
    if (patch?.sla) next.sla = { ...(base.sla ?? {}), ...patch.sla };
    if (patch?.customer) next.customer = { ...(base.customer ?? {}), ...patch.customer };
    if (Array.isArray(patch?.requestedDocs)) next.requestedDocs = [...patch.requestedDocs];
    if (Array.isArray(patch?.timeline)) next.timeline = patch.timeline;
    if (Array.isArray(patch?.messages)) next.messages = patch.messages;
    return next;
  };

  const ensureTicket = (ticketId) => {
    if (!ticketId) return emptyTicket("unknown");
    if (!ticketsById[ticketId]) {
      ticketsById = { ...ticketsById, [ticketId]: emptyTicket(ticketId) };
      bumpTicketOrder(ticketId);
    }
    return ticketsById[ticketId];
  };

  const touchTicket = (ticketId, timestamp = Date.now()) => {
    const ticket = ensureTicket(ticketId);
    const pulseId = timestamp;
    const updated = {
      ...ticket,
      pulse: pulseId,
      updatedAt: Math.max(ticket.updatedAt ?? 0, timestamp),
    };
    ticketsById = { ...ticketsById, [ticketId]: updated };
    bumpTicketOrder(ticketId);
    const timeoutId = setTimeout(() => {
      const current = ticketsById[ticketId];
      if (current?.pulse === pulseId) {
        ticketsById = { ...ticketsById, [ticketId]: { ...current, pulse: null } };
      }
      timers.delete(timeoutId);
    }, 1000);
    timers.add(timeoutId);
  };

  const appendTimeline = (ticketId, evt) => {
    const ticket = ensureTicket(ticketId);
    const entry = {
      id: `${evt.name}-${evt.timestamp}-${Math.random().toString(36).slice(2)}`,
      name: evt.name,
      timestamp: evt.timestamp,
      value: evt.value ?? {},
    };
    const existing = (ticket.timeline ?? []).some(
      (item) => item.name === entry.name && item.timestamp === entry.timestamp,
    );
    if (existing) return;
    const timeline = [entry, ...(ticket.timeline ?? [])].slice(0, MAX_TIMELINE);
    ticketsById = { ...ticketsById, [ticketId]: { ...ticket, timeline } };
  };

  const appendMessage = (ticketId, message) => {
    const ticket = ensureTicket(ticketId);
    const messages = Array.isArray(ticket.messages) ? [...ticket.messages] : [];
    const index = message.messageId ? messages.findIndex((msg) => msg.messageId === message.messageId) : -1;
    if (index >= 0) {
      messages[index] = { ...messages[index], ...message };
    } else {
      messages.push(message);
    }
    messages.sort((a, b) => (a.at ?? 0) - (b.at ?? 0));
    ticketsById = { ...ticketsById, [ticketId]: { ...ticket, messages } };
  };

  const ingestSummary = (summary) => {
    if (!summary?.ticketId) return;
    const ticket = ensureTicket(summary.ticketId);
    ticketsById = {
      ...ticketsById,
      [summary.ticketId]: mergeTicket(ticket, summary),
    };
  };

  const ingestDetail = (detail) => {
    if (!detail?.ticketId) return;
    const ticket = ensureTicket(detail.ticketId);
    ticketsById = {
      ...ticketsById,
      [detail.ticketId]: mergeTicket(ticket, { ...detail, detailFetchedAt: Date.now() }),
    };
  };

  const loadTickets = async () => {
    ticketsLoading = true;
    ticketsError = null;
    const result = await api.listTickets();
    if (!result.ok) {
      ticketsError = result.error || "No se pudo cargar el inbox";
      ticketsLoading = false;
      return;
    }
    const items = Array.isArray(result.data) ? result.data : [];
    const nextById = { ...ticketsById };
    const order = [];
    items.forEach((ticket) => {
      if (!ticket?.ticketId) return;
      const existing = nextById[ticket.ticketId] || emptyTicket(ticket.ticketId);
      nextById[ticket.ticketId] = mergeTicket(existing, ticket);
      order.push(ticket.ticketId);
    });
    ticketsById = nextById;
    ticketOrder = order;
    if (order.length === 0) {
      selectedTicketId = null;
    } else if (!selectedTicketId) {
      await selectTicket(order[0]);
    }
    ticketsLoading = false;
  };

  const fetchTicketDetail = async (ticketId, force = false) => {
    if (!ticketId) return;
    const lastFetched = lastFetchedByTicket[ticketId] ?? 0;
    if (!force && Date.now() - lastFetched < DETAIL_TTL_MS) return;
    detailLoading = true;
    detailError = null;
    const result = await api.getTicket(ticketId);
    if (!result.ok) {
      detailError = result.error || "No se pudo cargar el ticket";
      detailLoading = false;
      return;
    }
    ingestDetail(result.data);
    lastFetchedByTicket = { ...lastFetchedByTicket, [ticketId]: Date.now() };
    detailLoading = false;
  };

  const selectTicket = async (ticketId) => {
    if (!ticketId) return;
    selectedTicketId = ticketId;
    await fetchTicketDetail(ticketId, false);
  };

  const applyTicketPatch = (ticketId, patch, timestamp) => {
    const ticket = ensureTicket(ticketId);
    const mergedPatch = { ...patch };
    if (patch?.sla) {
      mergedPatch.sla = { ...(ticket.sla ?? {}), ...patch.sla };
    }
    const sanitizedPatch = Object.fromEntries(
      Object.entries(mergedPatch).filter(([, value]) => value !== undefined),
    );
    ticketsById = {
      ...ticketsById,
      [ticketId]: mergeTicket(ticket, { ...sanitizedPatch, updatedAt: timestamp }),
    };
  };

  const handleTicketEvent = (evt, ticketId) => {
    if (evt.name === "ticket.created" && evt.value?.ticket) {
      ingestDetail(evt.value.ticket);
      appendTimeline(ticketId, evt);
      return;
    }

    if (evt.name === "ticket.updated") {
      const patch = evt.value?.patch ?? {};
      applyTicketPatch(ticketId, patch, evt.timestamp);
      appendTimeline(ticketId, evt);
      return;
    }

    if (evt.name === "ticket.assigned") {
      applyTicketPatch(ticketId, { assignee: evt.value?.assignee, sla: evt.value?.sla }, evt.timestamp);
      appendTimeline(ticketId, evt);
      return;
    }

    if (evt.name === "ticket.sla.started") {
      const slaType = String(evt.value?.slaType || "").toUpperCase();
      const dueAt = evt.value?.dueAt;
      const sla = {};
      if (slaType === "ASSIGNMENT") {
        sla.assignmentDueAt = dueAt;
        sla.assignmentStartedAt = evt.timestamp;
      }
      if (slaType === "DOC_VALIDATION") {
        sla.docValidationDueAt = dueAt;
        sla.docValidationStartedAt = evt.timestamp;
      }
      applyTicketPatch(ticketId, { sla }, evt.timestamp);
      appendTimeline(ticketId, evt);
      return;
    }

    if (evt.name === "ticket.sla.breached") {
      const slaType = String(evt.value?.slaType || "").toUpperCase();
      const sla = {};
      if (slaType === "ASSIGNMENT") {
        sla.assignmentBreachedAt = evt.value?.breachedAt ?? evt.timestamp;
      }
      if (slaType === "DOC_VALIDATION") {
        sla.docValidationBreachedAt = evt.value?.breachedAt ?? evt.timestamp;
      }
      applyTicketPatch(ticketId, { sla, status: "ESCALATED" }, evt.timestamp);
      appendTimeline(ticketId, evt);
      return;
    }

    if (evt.name === "ticket.escalated") {
      applyTicketPatch(ticketId, { status: "ESCALATED" }, evt.timestamp);
      appendTimeline(ticketId, evt);
      return;
    }

    if (evt.name === "ticket.closed") {
      applyTicketPatch(ticketId, { status: "CLOSED" }, evt.timestamp);
      appendTimeline(ticketId, evt);
      return;
    }

    appendTimeline(ticketId, evt);
  };

  const handleMessagingEvent = (evt, ticketId) => {
    const value = evt.value ?? {};
    if (evt.name === "messaging.delivery") {
      if (value.messageId) {
        appendMessage(ticketId, { messageId: value.messageId, status: value.status, at: value.at ?? evt.timestamp });
      }
      return;
    }
    const isInbound = evt.name === "messaging.inbound" || evt.name === "messaging.inbound.raw";
    const isOutbound = evt.name === "messaging.outbound";
    const at = value.receivedAt ?? value.sentAt ?? value.at ?? evt.timestamp;
    const message = {
      direction: isOutbound ? "outbound" : "inbound",
      provider: value.provider,
      channel: value.channel,
      messageId: value.messageId,
      text: value.text,
      at,
      mediaCount: value.mediaCount ?? 0,
      status: value.status,
    };
    appendMessage(ticketId, message);
    if (message.text) {
      applyTicketPatch(ticketId, { lastMessageText: message.text, lastMessageAt: at }, evt.timestamp);
    }
  };

  const handleWorkflowEvent = (evt) => {
    if (evt.name === "workflow.reset") {
      addToast("Workflow reiniciado", "info");
      ticketsById = {};
      ticketOrder = [];
      selectedTicketId = null;
      return;
    }
    if (evt.name === "workflow.error") {
      addToast("Workflow en error", "error");
    }
  };

  const applyEvent = (incoming) => {
    const evt = normalizeEvent(incoming);
    liveEvents = [evt, ...liveEvents].slice(0, MAX_LIVE_EVENTS);

    if (evt.name?.startsWith("workflow.")) {
      handleWorkflowEvent(evt);
    }

    if (evt.name === "messaging.inbound.raw") {
      return;
    }

    const ticketId = getEventTicketId(evt);
    if (!ticketId) return;
    lastEventByTicket = { ...lastEventByTicket, [ticketId]: evt.timestamp };
    touchTicket(ticketId, evt.timestamp);

    if (isTicketEvent(evt.name)) {
      handleTicketEvent(evt, ticketId);
    }
    if (isMessagingEvent(evt.name)) {
      handleMessagingEvent(evt, ticketId);
    }
  };

  const scheduleFallbackRefetch = (ticketId, startedAt) => {
    const timeoutId = setTimeout(() => {
      const lastEvent = lastEventByTicket[ticketId] ?? 0;
      if (lastEvent < startedAt) {
        fetchTicketDetail(ticketId, true);
      }
      timers.delete(timeoutId);
    }, 500);
    timers.add(timeoutId);
  };

  const runTicketAction = async (ticketId, action) => {
    if (!ticketId) return;
    const startedAt = Date.now();
    const result = await action();
    if (!result.ok) {
      addToast(result.error || "Accion fallida", "error");
      return;
    }
    scheduleFallbackRefetch(ticketId, startedAt);
  };

  const assignAdmin = (ticketId) =>
    runTicketAction(ticketId, () => api.assignTicket(ticketId, { team: "ADMIN", name: "Admin - Lucía" }));

  const requestDocs = (ticketId, requestedDocs = DEFAULT_REQUESTED_DOCS) =>
    runTicketAction(ticketId, () => api.docsAction(ticketId, { action: "REQUEST", requestedDocs }));

  const receiveDocs = (ticketId) => runTicketAction(ticketId, () => api.docsAction(ticketId, { action: "RECEIVE" }));

  const closeWithDocs = (ticketId) =>
    runTicketAction(ticketId, () =>
      api.closeTicket(ticketId, {
        resolutionCode: "DOCS_VALIDATED",
        notes: "Documentacion validada",
      }),
    );

  const escalateTicket = (ticketId) =>
    runTicketAction(ticketId, () => api.escalateTicket(ticketId, { reason: "MANUAL", toTeam: "SUPERVISOR" }));

  const simulateBreach = (ticketId, slaType) =>
    runTicketAction(ticketId, () => api.simulateBreach(ticketId, { slaType }));

  const resetDemo = async () => {
    const result = await api.resetDemo();
    if (!result.ok) {
      addToast(result.error || "No se pudo resetear", "error");
      return;
    }
    addToast("Reset enviado. Esperando eventos...", "info");
  };

  const init = async () => {
    await loadTickets();
  };

  const teardown = () => {
    timers.forEach((timer) => clearTimeout(timer));
    timers.clear();
  };

  return {
    get ticketsById() {
      return ticketsById;
    },
    get ticketOrder() {
      return ticketOrder;
    },
    get ticketsLoading() {
      return ticketsLoading;
    },
    get ticketsError() {
      return ticketsError;
    },
    get detailLoading() {
      return detailLoading;
    },
    get detailError() {
      return detailError;
    },
    get selectedTicketId() {
      return selectedTicketId;
    },
    get selectedTicket() {
      return selectedTicketId ? ticketsById[selectedTicketId] : null;
    },
    get tickets() {
      return ticketOrder.map((id) => ticketsById[id]).filter(Boolean);
    },
    get liveEvents() {
      return liveEvents;
    },
    get filters() {
      return filters;
    },
    get search() {
      return search;
    },
    get toasts() {
      return toasts;
    },
    get sse() {
      return sse;
    },
    setSseConnected,
    setFilters: (next) => (filters = { ...filters, ...next }),
    setSearch: (value) => (search = value),
    selectTicket,
    refreshTickets: loadTickets,
    fetchTicketDetail,
    applyEvent,
    assignAdmin,
    requestDocs,
    receiveDocs,
    closeWithDocs,
    escalateTicket,
    simulateBreach,
    resetDemo,
    init,
    teardown,
    addToast,
  };
}

export const workflow = createWorkflowState();
