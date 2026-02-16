import { listRuns, startRun } from "./api";
import { WORKFLOW_ID, normalizePayload } from "./types";

const MAX_SSE_EVENTS = 300;
const MAX_SUMMARY = 160;
const MAX_DATA_CHARS = 900;
const MAX_STEPS = 200;
const MAX_INBOUND = 50;
const NODE_ORDER = [
  "normalize_input",
  "intent_classify",
  "extract_entities",
  "pragmatics",
  "decide_next",
  "build_response",
];

const truncate = (text, max = MAX_SUMMARY) => {
  if (!text) return "";
  const value = String(text);
  if (value.length <= max) return value;
  return `${value.slice(0, max - 3).trim()}...`;
};

const clamp = (items, max) => items.slice(0, max);

const compactData = (value) => {
  if (!value || typeof value !== "object") return value;
  try {
    const text = JSON.stringify(value);
    if (text.length <= MAX_DATA_CHARS) return value;
    return {
      preview: `${text.slice(0, MAX_DATA_CHARS - 3)}...`,
      truncated: true,
    };
  } catch (err) {
    return { truncated: true };
  }
};

const normalizeTimelineEvent = (evt) => {
  const name = evt?.type || evt?.eventType || evt?.name || "unknown";
  const timestamp = evt?.ts || evt?.timestamp || Date.now();
  const value = evt?.value ?? evt?.data ?? evt?.payload ?? {};
  const summary = truncate(value?.summary || value?.status || name);
  const data = value?.data ? compactData(value.data) : compactData(value);
  return {
    id: `${name}-${timestamp}-${Math.random().toString(36).slice(2)}`,
    name,
    timestamp,
    correlationId: evt?.raw?.correlationId ?? value?.runId ?? evt?.correlationId ?? null,
    summary,
    data,
  };
};

const getRunId = (payload, evt) =>
  payload?.runId || payload?.run_id || payload?.id || evt?.raw?.correlationId || evt?.correlationId || null;

const buildStep = (payload) => ({
  nodeId: payload?.nodeId || payload?.node_id || null,
  status: payload?.status || "unknown",
  startedAt: payload?.startedAt ?? null,
  endedAt: payload?.endedAt ?? null,
  summary: payload?.summary || "",
  data: payload?.data || {},
});

const inferNodeId = (steps) => {
  if (!Array.isArray(steps) || steps.length === 0) return null;
  const last = steps[steps.length - 1];
  if (last?.nodeId) return last.nodeId;
  const idx = Math.min(steps.length, NODE_ORDER.length) - 1;
  return NODE_ORDER[idx] || null;
};

const isWamid = (value) => typeof value === "string" && value.startsWith("wamid");

export function createStudioState() {
  let inputText = $state("");
  let runsById = $state({});
  let runOrder = $state([]);
  let activeRunId = $state(null);
  let activeNodeId = $state(null);
  let sseEvents = $state([]);
  let inboundMessages = $state([]);
  let connectionStatus = $state("disconnected");
  let sseConnected = $state(false);
  let lastEventAt = $state(null);
  let eventCount = $state(0);
  let activeTicketId = $state(null);
  let busy = $state(false);
  let autoFocusNewest = $state(true);

  const runs = $derived(runOrder.map((runId) => runsById[runId]).filter(Boolean));
  const activeRun = $derived((activeRunId && runsById[activeRunId]) || null);
  const activeOutput = $derived(activeRun?.output || {});
  const activeSteps = $derived(activeRun?.steps || []);
  const activeInputLen = $derived((activeRun?.input || "").length);
  const stepsByNodeId = $derived.by(() => {
    const map = {};
    for (const step of activeSteps || []) {
      if (!step?.nodeId) continue;
      map[step.nodeId] = {
        status: step.status || "completed",
        startedAt: step.startedAt ?? null,
        endedAt: step.endedAt ?? null,
        summary: step.summary || "",
        data: step.data || {},
      };
    }
    return map;
  });

  const setInputText = (value) => {
    inputText = value ?? "";
  };

  const setConnectionStatus = (status) => {
    connectionStatus = status === "connected" ? "connected" : "disconnected";
    sseConnected = connectionStatus === "connected";
  };

  const touchRunOrder = (runId) => {
    if (!runId) return;
    if (!runOrder.includes(runId)) {
      runOrder = [runId, ...runOrder];
      return;
    }
    if (runOrder[0] !== runId) {
      runOrder = [runId, ...runOrder.filter((id) => id !== runId)];
    }
  };

  const upsertRun = (runId, patch) => {
    if (!runId) return null;
    const current = runsById[runId] || {
      runId,
      status: "RUNNING",
      steps: [],
      output: null,
    };
    const next = { ...current, ...patch };
    // Ensure deep updates for steps if provided in patch
    if (patch.steps) {
      next.steps = patch.steps;
    }
    runsById = { ...runsById, [runId]: next };
    touchRunOrder(runId);
    return next;
  };

  const appendStep = (run, step) => {
    const steps = [...(run.steps || []), step];
    const trimmed = steps.length > MAX_STEPS ? steps.slice(steps.length - MAX_STEPS) : steps;
    return { ...run, steps: trimmed };
  };

  const applySseEvent = (evt) => {
    const eventType = evt?.type || evt?.eventType || evt?.name;
    if (!eventType) return;
    const payload = normalizePayload(evt);

    if (eventType === "messaging.inbound" || eventType === "messaging.inbound.raw") {
      if (payload?.ticketId) {
        activeTicketId = payload.ticketId;
      }
      const messageId = payload?.messageId || payload?.message_id || payload?.wamid || null;
      if (messageId && isWamid(messageId)) {
        if (inboundMessages.some((message) => message.messageId === messageId)) return;
      }
      const timestamp = payload?.receivedAt || evt?.ts || Date.now();
      const inbound = {
        id: `${messageId || "inbound"}-${timestamp}-${Math.random().toString(36).slice(2)}`,
        messageId,
        correlationId: evt?.raw?.correlationId ?? evt?.correlationId ?? null,
        from: payload?.from || payload?.wa_id || "--",
        text: (typeof payload?.text === "object" ? payload?.text?.body : payload?.text) || "",
        timestamp,
      };
      inboundMessages = clamp([inbound, ...inboundMessages], MAX_INBOUND);
      return;
    }

    if (eventType === "messaging.outbound" && payload?.ticketId) {
      activeTicketId = payload.ticketId;
      return;
    }

    if (eventType === "human.action_required") {
      if (payload?.ticket_id) {
        activeTicketId = payload.ticket_id;
      } else if (payload?.ticketId) {
        activeTicketId = payload.ticketId;
      }
      return;
    }

    if (!eventType.startsWith("ai_workflow.")) return;

    const runId = getRunId(payload, evt);
    if (!runId) return;

    if (eventType === "ai_workflow.run.started") {
      const nextRun = upsertRun(runId, {
        runId, // Ensure runId is set
        workflowId: payload?.workflowId,
        input: payload?.input || "",
        status: "RUNNING",
        startedAt: payload?.startedAt ?? evt?.ts ?? Date.now(),
        updatedAt: Date.now(),
        steps: [],
        output: null,
        error: null,
      });
      if (autoFocusNewest) {
        activeRunId = runId;
      }
      activeNodeId = payload?.nodeId || "normalize_input";
      return nextRun;
    }

    if (eventType === "ai_workflow.run.step") {
      // Ensure run exists, create if not (could happen if missed started)
      let current = runsById[runId];
      if (!current) {
        current = upsertRun(runId, { runId, status: "RUNNING", steps: [] });
      }

      const step = buildStep(payload);
      let next = appendStep(current, step);

      const stepData = step.data || {};
      const patch = {};
      if (stepData.primaryIntent) patch.primaryIntent = stepData.primaryIntent;
      if (stepData.secondaryIntents) patch.secondaryIntents = stepData.secondaryIntents;
      if (stepData.speechAct) patch.speechAct = stepData.speechAct;
      if (Number.isFinite(stepData.missingSlotsCount)) {
        patch.missingSlotsCount = stepData.missingSlotsCount;
      }
      const status = payload?.status || next.status || "RUNNING";
      next = { ...next, ...patch, status };
      runsById = { ...runsById, [runId]: next };
      touchRunOrder(runId);

      if (autoFocusNewest) {
        activeRunId = runId;
      }
      activeNodeId = step.nodeId || inferNodeId(next.steps) || null;

      return next;
    }

    if (eventType === "ai_workflow.run.completed") {
      // Edge case: if runId not exists, create skeleton
      const exists = !!runsById[runId];
      // If NOT exists, we patch input as "(unknown)" and steps as []
      // If exists, we don't overwrite input/steps unless patch has them (we don't pass them here)
      const skeletonPatch = exists ? {} : { input: "(unknown)", steps: [] };

      const nextRun = upsertRun(runId, {
        ...skeletonPatch,
        status: "COMPLETED",
        output: payload?.output || null,
        endedAt: payload?.endedAt ?? evt?.ts ?? Date.now(),
        updatedAt: Date.now(),
      });
      if (autoFocusNewest) {
        activeRunId = runId;
      }
      activeNodeId = null;
      return nextRun;
    }

    if (eventType === "ai_workflow.run.failed") {
      const nextRun = upsertRun(runId, {
        status: "FAILED",
        error: payload?.error || payload?.message || "Failed",
        endedAt: payload?.at ?? evt?.ts ?? Date.now(),
        updatedAt: Date.now(),
      });
      if (autoFocusNewest) {
        activeRunId = runId;
      }
      activeNodeId = null;
      return nextRun;
    }

    return null;
  };

  const pushSseEvent = (evt) => {
    const normalized = normalizeTimelineEvent(evt);
    sseEvents = clamp([normalized, ...sseEvents], MAX_SSE_EVENTS);
  };

  const noteSseEvent = (evt) => {
    eventCount += 1;
    lastEventAt = evt?.ts || evt?.timestamp || Date.now();
  };

  const refreshRuns = async () => {
    const result = await listRuns();
    if (!result.ok) return;
    const items = Array.isArray(result.data) ? result.data : [];
    const nextById = {};
    const nextOrder = [];

    // Preserve existing runs that are not in the list if needed? usually list is source of truth
    // But for stream we might have newer ones?
    // Let's just merge.

    for (const run of items) {
      if (!run?.runId) continue;
      const existing = runsById[run.runId] || {};
      nextById[run.runId] = {
        ...existing,
        ...run,
        steps: existing.steps || [], // steps might not be in listRun detailed? Assuming they are or we keep existing
        output: run.output ?? existing.output ?? null,
      };
      nextOrder.push(run.runId);
    }

    // Sort? runOrder usually chronological or reverse?
    // Prompt says: Listar runs en orden inverso (último primero) usando runOrder.
    // If API returns list, we assume it's sorted or we trust the API order?
    // Usually we want newest first.
    // Let's assume API returns random or chronological.
    // We already have `touchRunOrder` which puts newest at top.
    // If I replace `runsById`, I should be careful.

    // Merge strategy:
    // Keep existing `runsById` and update fields.
    // Rebuild `runOrder` based on list + what we have? 
    // Best: just use `upsertRun` for each item to merge properly and handle order.

    for (const run of items) {
      upsertRun(run.runId, run);
    }

    if (!activeRunId && runOrder.length) {
      activeRunId = runOrder[0];
    }
  };

  const handleStartRun = async () => {
    if (!inputText.trim() || busy) return;
    busy = true;
    const result = await startRun({ input: inputText, workflowId: WORKFLOW_ID, mode: "heuristic" });
    busy = false;
    if (!result.ok) {
      console.error("Failed to start run:", result.error);
      return;
    }
    const run = result.data;
    if (run?.runId) {
      autoFocusNewest = true;
      upsertRun(run.runId, {
        ...run,
        steps: run.steps || [],
      });
      activeRunId = run.runId;
      activeNodeId = "normalize_input"; // Default start
    }
  };

  const setActiveRunId = (runId) => {
    if (!runId || !runsById[runId]) return;
    activeRunId = runId;
    autoFocusNewest = false; // Disable auto focus when user manually selects
    // activeNodeId = inferNodeId(runsById[runId]?.steps) || null; // Optionally reset active node?
    // Prompt says: Click cambia activeRunId y setea autoFocusNewest=false. nothing about node.
  };

  const setActiveTicketId = (ticketId) => {
    activeTicketId = ticketId || null;
  };

  return {
    get inputText() { return inputText; },
    get runsById() { return runsById; },
    get runOrder() { return runOrder; },
    get runs() { return runs; },
    get activeRunId() { return activeRunId; },
    get activeRun() { return activeRun; },
    get activeOutput() { return activeOutput; },
    get activeSteps() { return activeSteps; },
    get activeInputLen() { return activeInputLen; },
    get stepsByNodeId() { return stepsByNodeId; },
    get activeNodeId() { return activeNodeId; },
    get sseEvents() { return sseEvents; },
    get inboundMessages() { return inboundMessages; },
    get connectionStatus() { return connectionStatus; },
    get sseConnected() { return sseConnected; },
    get lastEventAt() { return lastEventAt; },
    get eventCount() { return eventCount; },
    get activeTicketId() { return activeTicketId; },
    get busy() { return busy; },
    setInputText,
    setConnectionStatus,
    refreshRuns,
    startRun: handleStartRun,
    setActiveRunId,
    setActiveTicketId,
    applySseEvent,
    pushSseEvent,
    noteSseEvent,
    clearEvents: () => {
      sseEvents = [];
      eventCount = 0;
      lastEventAt = null;
    },
    setAutoFocusNewest: (val) => { autoFocusNewest = !!val; },
    get autoFocusNewest() { return autoFocusNewest; }
  };
}

export const studio = createStudioState();
