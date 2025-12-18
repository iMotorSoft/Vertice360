import * as api from "./api";

// NOTE: Avoid naming consuming variables `state` to prevent $store auto-subscribe collisions with the $state rune.
const stageConfig = [
  { id: "stage-contacted", title: "New" },
  { id: "stage-qualification", title: "Qualified" },
  { id: "stage-visit", title: "Visit Scheduled" },
  { id: "stage-offer", title: "Offer" },
  { id: "stage-won", title: "Won" },
  { id: "stage-lost", title: "Lost" },
];

const toastId = () => crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);

export function createCrmState() {
  let conversations = $state([]);
  let conversationsLoading = $state(true);
  let conversationsError = $state(null);
  let selectedConversationId = $state(null);
  let selectedConversation = $state(null);
  let conversationLoading = $state(false);

  let pipeline = $state([]);
  let pipelineLoading = $state(true);
  let pipelineError = $state(null);

  let tasks = $state([]);
  let tasksLoading = $state(true);
  let tasksError = $state(null);

  let search = $state("");
  let channelFilter = $state("all");

  let timeline = $state([]);
  let toasts = $state([]);
  let sse = $state({ connected: false, lastChangeMs: 0 });

  const addToast = (message, tone = "info") => {
    const id = toastId();
    toasts = [...toasts, { id, message, tone }];
    setTimeout(() => {
      toasts = toasts.filter((t) => t.id !== id);
    }, 3600);
  };

  const setSseStatus = (connected) => {
    sse = { connected, lastChangeMs: Date.now() };
  };

  const normalizeTimelineEntry = (entry) => ({
    ...entry,
    ts: entry.ts ?? Date.now(),
  });

  const setTimelineFromConversation = (conv) => {
    if (!conv) {
      timeline = [];
      return;
    }
    timeline = (conv.messages ?? [])
      .map((msg) =>
        normalizeTimelineEntry({
          id: `msg-${msg.id}`,
          ts: new Date(msg.ts).getTime(),
          type: "message",
          actor: msg.sender,
          text: msg.text,
          meta: msg.status,
        }),
      )
      .sort((a, b) => b.ts - a.ts);
  };

  const appendTimeline = (entry) => {
    const normalized = normalizeTimelineEntry(entry);
    const existing = timeline.find((t) => t.id === normalized.id);
    if (existing) {
      timeline = timeline.map((t) => (t.id === normalized.id ? normalized : t)).sort((a, b) => b.ts - a.ts);
    } else {
      timeline = [normalized, ...timeline].sort((a, b) => b.ts - a.ts);
    }
  };

  const loadConversations = async () => {
    conversationsLoading = true;
    conversationsError = null;
    try {
      conversations = await api.fetchConversations();
      if (!selectedConversationId && conversations.length > 0) {
        await selectConversation(conversations[0].id);
      }
    } catch (err) {
      conversationsError = err instanceof Error ? err.message : "Error desconocido";
    } finally {
      conversationsLoading = false;
    }
  };

  const selectConversation = async (conversationId) => {
    if (!conversationId) return;
    selectedConversationId = conversationId;
    conversationLoading = true;
    try {
      selectedConversation = await api.fetchConversation(conversationId);
      setTimelineFromConversation(selectedConversation);
    } catch (err) {
      addToast(err instanceof Error ? err.message : "No se pudo cargar la conversación", "error");
    } finally {
      conversationLoading = false;
    }
  };

  const loadPipeline = async () => {
    pipelineLoading = true;
    pipelineError = null;
    try {
      pipeline = await api.fetchPipeline();
    } catch (err) {
      pipelineError = err instanceof Error ? err.message : "Error al cargar pipeline";
    } finally {
      pipelineLoading = false;
    }
  };

  const loadTasks = async () => {
    tasksLoading = true;
    tasksError = null;
    try {
      tasks = await api.fetchTasks();
    } catch (err) {
      tasksError = err instanceof Error ? err.message : "Error al cargar tareas";
    } finally {
      tasksLoading = false;
    }
  };

  const refreshAll = async () => {
    await Promise.all([loadConversations(), loadPipeline(), loadTasks()]);
    if (selectedConversationId) {
      await selectConversation(selectedConversationId);
    }
  };

  const updateConversationPreview = (conversationId, updater) => {
    conversations = conversations.map((conv) => {
      if (conv.id !== conversationId) return conv;
      const updated = typeof updater === "function" ? updater(conv) : conv;
      return { ...updated };
    });
  };

  const handleNewMessage = (message, ts = Date.now()) => {
    updateConversationPreview(message.conversationId, (conv) => {
      const messages = conv.messages ? [...conv.messages, message] : [message];
      return { ...conv, messages };
    });

    if (selectedConversation?.id === message.conversationId) {
      selectedConversation = {
        ...selectedConversation,
        messages: [...(selectedConversation.messages ?? []), message],
      };
      appendTimeline({
        id: `msg-${message.id}`,
        ts,
        type: "message",
        actor: message.sender,
        text: message.text,
        meta: message.status,
      });
    }
  };

  const handleMessageStatus = (message, ts = Date.now()) => {
    const applyStatus = (msgs = []) => msgs.map((m) => (m.id === message.id ? { ...m, status: message.status } : m));
    updateConversationPreview(message.conversationId, (conv) => ({ ...conv, messages: applyStatus(conv.messages) }));
    if (selectedConversation?.id === message.conversationId) {
      selectedConversation = {
        ...selectedConversation,
        messages: applyStatus(selectedConversation.messages),
      };
      appendTimeline({
        id: `msg-${message.id}`,
        ts,
        type: "message-status",
        actor: message.sender,
        text: `Estado: ${message.status}`,
      });
    }
  };

  const handleDealStageChanged = (deal, ts = Date.now()) => {
    pipeline = pipeline.map((d) => (d.id === deal.id ? { ...d, stageId: deal.stageId } : d));
    appendTimeline({
      id: `deal-${deal.id}-${deal.stageId}`,
      ts,
      type: "deal",
      text: `${deal.title} → ${deal.stageId}`,
    });
  };

  const handleTaskEvent = (task, type, ts = Date.now()) => {
    const exists = tasks.find((t) => t.id === task.id);
    if (exists) {
      tasks = tasks.map((t) => (t.id === task.id ? task : t));
    } else {
      tasks = [task, ...tasks];
    }
    appendTimeline({
      id: `task-${task.id}-${type}`,
      ts,
      type: "task",
      text: `${task.title} (${type === "task.completed" ? "completada" : "creada"})`,
    });
    addToast(`${task.title} (${type === "task.completed" ? "completada" : "creada"})`, "info");
  };

  const sendMessage = async (text) => {
    if (!selectedConversationId) return;
    const trimmed = text.trim();
    if (!trimmed) return;
    try {
      const msg = await api.sendMessage(selectedConversationId, trimmed);
      handleNewMessage(msg);
      addToast("Mensaje enviado", "success");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "No se pudo enviar", "error");
    }
  };

  const simulateInbound = async (channel, text) => {
    if (!selectedConversationId) return;
    try {
      await api.simulateInbound({ channel, conversationId: selectedConversationId, text });
      addToast("Mensaje simulado", "success");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "No se pudo simular", "error");
    }
  };

  const moveDealToStage = async (dealId, stageId) => {
    try {
      const deal = await api.moveDeal(dealId, stageId);
      pipeline = pipeline.map((d) => (d.id === deal.id ? deal : d));
      appendTimeline({ id: `deal-${deal.id}-${stageId}`, ts: Date.now(), type: "deal", text: `${deal.title} → ${stageId}` });
      addToast("Deal movido", "success");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "No se pudo mover el deal", "error");
      await loadPipeline();
    }
  };

  const createNewTask = async ({ title, leadId, dealId, dueAt }) => {
    try {
      const task = await api.createTask({ title, leadId, dealId, dueAt });
      tasks = [task, ...tasks];
      appendTimeline({ id: `task-${task.id}`, ts: Date.now(), type: "task", text: `${task.title} creada` });
      addToast("Tarea creada", "success");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "No se pudo crear la tarea", "error");
    }
  };

  const completeTask = async (taskId) => {
    try {
      const task = await api.completeTask(taskId);
      tasks = tasks.map((t) => (t.id === task.id ? task : t));
      appendTimeline({ id: `task-${task.id}-completed`, ts: Date.now(), type: "task", text: `${task.title} completada` });
      addToast("Tarea completada", "success");
    } catch (err) {
      addToast(err instanceof Error ? err.message : "No se pudo completar la tarea", "error");
    }
  };

  const handleSseEvent = ({ name, value, raw }) => {
    const ts = raw?.timestamp ?? Date.now();
    if (name === "conversation.message.new") {
      handleNewMessage(value, ts);
    }
    if (name === "conversation.message.status") {
      handleMessageStatus(value, ts);
    }
    if (name === "deal.stage.changed") {
      handleDealStageChanged(value, ts);
    }
    if (name === "task.created" || name === "task.completed") {
      handleTaskEvent(value, name, ts);
    }
  };

  const init = async () => {
    await Promise.all([loadConversations(), loadPipeline(), loadTasks()]);
  };

  const teardown = () => { };

  return {
    // state (getters keep reactivity)
    get conversations() {
      return conversations;
    },
    get conversationsLoading() {
      return conversationsLoading;
    },
    get conversationsError() {
      return conversationsError;
    },
    get selectedConversationId() {
      return selectedConversationId;
    },
    get selectedConversation() {
      return selectedConversation;
    },
    get conversationLoading() {
      return conversationLoading;
    },
    get pipeline() {
      return pipeline;
    },
    get pipelineLoading() {
      return pipelineLoading;
    },
    get pipelineError() {
      return pipelineError;
    },
    get tasks() {
      return tasks;
    },
    get tasksLoading() {
      return tasksLoading;
    },
    get tasksError() {
      return tasksError;
    },
    get search() {
      return search;
    },
    get channelFilter() {
      return channelFilter;
    },
    get timeline() {
      return timeline;
    },
    get toasts() {
      return toasts;
    },
    get sse() {
      return sse;
    },
    get sseConnected() {
      return sse.connected;
    },
    setSseConnected: setSseStatus,
    handleSseEvent,
    get stageConfig() {
      return stageConfig;
    },
    // actions
    setChannelFilter: (value) => (channelFilter = value),
    setSearch: (value) => (search = value),
    selectConversation,
    refreshAll,
    sendMessage,
    simulateInbound,
    moveDealToStage,
    createNewTask,
    completeTask,
    setTimelineFromConversation,
    init,
    teardown,
    addToast,
  };
}

export const crm = createCrmState();
