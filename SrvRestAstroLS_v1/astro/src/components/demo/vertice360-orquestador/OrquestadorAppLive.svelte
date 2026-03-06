<script>
  import { onMount } from "svelte";
  import { createSseManager } from "../../../lib/shared/sse.js";
  import { URL_SSE, URL_SVG_XMLNS, URL_WA_API, URL_WA_ME } from "../../global.js";

  import LeadDetailModal from "./LeadDetailModal.svelte";
  import VisitProposalModal from "./VisitProposalModal.svelte";
  import {
    bootstrap,
    confirmVisit,
    dashboard,
    proposeVisit,
    rescheduleVisit,
    supervisorSend,
    ticketDetail,
  } from "../../../lib/vertice360_orquestador/api.js";

  let { initialCliente = "" } = $props();

  const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  const STAGE_WAITING_CONFIRMATION = "Esperando confirmación";

  let cliente = $state(String(initialCliente || "").trim());
  let notice = $state("");
  let errorMessage = $state("");
  let whatsappPhoneError = $state("");

  let isBootstrapping = $state(false);
  let isLoadingDashboard = $state(false);
  let isActionRunning = $state(false);

  let demoWhatsAppPhone = $state("");
  let ads = $state([]);
  let kpis = $state([]);
  let conversations = $state([]);

  let modalOpen = $state(false);
  let visitModalMode = $state("proponer");
  let selectedConversation = $state(null);
  let visitInitialValues = $state({
    advisor: "Asesor Demo",
    option1: "",
    option2: "",
    option3: "",
    message: "",
  });

  let detailModalOpen = $state(false);
  let selectedLead = $state(null);
  let detailMessages = $state([]);
  let detailMessagesLoading = $state(false);
  let supervisorSending = $state(false);

  let detailByTicket = $state({});
  let detailLoadingByTicket = $state({});
  let activeProposalByTicket = $state({});

  let bootstrapLoaded = $state(false);
  const WHATSAPP_PHONE_LOAD_ERROR = "No se pudo cargar el número de WhatsApp demo";
  const SSE_REFRESH_EVENTS = new Set(["messaging.inbound", "messaging.inbound.raw", "messaging.outbound"]);
  let sseConnected = $state(false);
  let pendingDashboardRefresh = false;
  let refreshTimer = null;

  const normalizeClienteDisplay = (value) => {
    const compact = String(value || "").replace(/[\s-]+/g, "");
    if (!compact) return "";
    const withoutPlus = compact.replace(/^\++/, "");
    if (!withoutPlus) return "";
    return `+${withoutPlus}`;
  };

  const hasCliente = () => Boolean(normalizeClienteDisplay(cliente));

  const normalizePhoneDigits = (value) => String(value || "").replace(/\D+/g, "");
  const hasDemoWhatsAppPhone = () => Boolean(normalizePhoneDigits(demoWhatsAppPhone));

  const shouldRefreshFromSseEvent = (evt) => {
    if (!evt || !SSE_REFRESH_EVENTS.has(String(evt.name || ""))) return false;
    return hasCliente();
  };

  const scheduleDashboardRefresh = () => {
    if (!hasCliente()) return;
    if (isLoadingDashboard) {
      pendingDashboardRefresh = true;
      return;
    }

    if (refreshTimer) {
      clearTimeout(refreshTimer);
    }
    refreshTimer = setTimeout(() => {
      refreshTimer = null;
      void loadDashboard({ silent: true });
    }, 220);
  };

  const formatDateTime = (value) => {
    if (!value) return "--";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "--";
    return DATE_TIME_FORMATTER.format(parsed).replace(",", "");
  };

  const toIsoOrNull = (value) => {
    const clean = String(value || "").trim();
    if (!clean) return null;
    const parsed = new Date(clean);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed.toISOString();
  };

  const toInputDateTime = (value) => {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "";
    return parsed.toISOString();
  };

  const extractProjectBarrio = (projectName, projectLocation) => {
    const locationBarrio = String(projectLocation?.barrio || "").trim();
    if (locationBarrio) return locationBarrio;

    const name = String(projectName || "").trim();
    if (!name) return "";

    const byDash = name.split("—").map((part) => part.trim()).filter(Boolean);
    if (byDash.length > 1) return byDash[1];

    const byHyphen = name.split("-").map((part) => part.trim()).filter(Boolean);
    if (byHyphen.length > 1) return byHyphen[1];

    return "";
  };

  const buildAdPrefillText = (ad) => {
    const projectCode = String(ad?.projectCode || "").trim();
    if (!projectCode) return "Hola, vengo por un anuncio.";
    const barrio = String(ad?.barrio || "").trim();
    if (barrio) {
      return `Hola, vengo por un anuncio. Me interesa ${projectCode} (${barrio}).`;
    }
    return `Hola, vengo por un anuncio. Me interesa ${projectCode}.`;
  };

  const isLikelyMobileBrowser = () => {
    if (typeof navigator === "undefined") return true;
    return /Android|iPhone|iPad|iPod|IEMobile|Opera Mini|Mobile/i.test(String(navigator.userAgent || ""));
  };

  const buildWhatsAppUrl = (toPhoneE164OrDigits, text) => {
    const digits = normalizePhoneDigits(toPhoneE164OrDigits);
    if (!digits) return "";
    const encodedText = encodeURIComponent(String(text || "").trim());
    if (isLikelyMobileBrowser()) {
      return `${URL_WA_ME}/${digits}?text=${encodedText}`;
    }
    return `${URL_WA_API}?phone=${digits}&text=${encodedText}`;
  };

  const getAdWhatsAppUrl = (ad) => {
    if (!hasDemoWhatsAppPhone()) return "";
    return buildWhatsAppUrl(demoWhatsAppPhone, buildAdPrefillText(ad));
  };

  const estadoLabel = (estado) => {
    if (estado === STAGE_WAITING_CONFIRMATION) return "Esperando conf.";
    return estado;
  };

  const estadoBadge = (estado) => {
    if (estado === "Nuevo") return "bg-sky-100 text-sky-700 border-sky-200";
    if (estado === "En seguimiento")
      return "bg-amber-100 text-amber-700 border-amber-200";
    if (estado === "Pendiente de visita")
      return "bg-violet-100 text-violet-700 border-violet-200";
    if (estado === STAGE_WAITING_CONFIRMATION)
      return "bg-pink-100 text-pink-700 border-pink-200";
    if (estado === "Visita confirmada")
      return "bg-emerald-100 text-emerald-700 border-emerald-200";
    return "bg-slate-100 text-slate-500 border-slate-200";
  };

  const isWaitingConfirmation = (estado) =>
    estado === STAGE_WAITING_CONFIRMATION || estado === "Esperando conf.";
  const isVisitConfirmed = (estado) => estado === "Visita confirmada";
  const isPendingVisit = (estado) => estado === "Pendiente de visita";
  const isGeneralFollowUp = (estado) =>
    estado === "Nuevo" ||
    estado === "En seguimiento" ||
    estado === "Esperando respuesta";

  const actionClass = (tone) => {
    const base =
      "btn btn-sm min-h-11 md:btn-xs md:min-h-[28px] hover:bg-gray-200 rounded-full p-2";
    if (tone === "primary") return `${base}`;
    if (tone === "success") return `${base}`;
    if (tone === "outline") return `${base}`;
    return `${base}`;
  };

  const actionIcon = (id) => {
    if (id === "visit")
      return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`;
    if (id === "confirm")
      return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4"><polyline points="20 6 9 17 4 12"/></svg>`;
    if (id === "reschedule")
      return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.5"/></svg>`;
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
  };

  const actionLabel = (id) => {
    if (id === "visit") return "Proponer visita";
    if (id === "confirm") return "Confirmar visita";
    if (id === "reschedule") return "Reagendar";
    return "Ver detalle";
  };

  const getConversationDateInfo = (row) => {
    if (row.estado === "Visita confirmada" && row.visitAt) {
      return {
        primary: `Visita: ${formatDateTime(row.visitAt)}`,
        secondary: "",
      };
    }

    const activityAt = row.lastActivityAt || row.createdAt;
    return {
      primary: activityAt
        ? `Último: ${formatDateTime(activityAt)}`
        : "Sin actividad",
      secondary:
        row.estado === STAGE_WAITING_CONFIRMATION && row.nextVisitProposalAt
          ? `Propuesta: ${formatDateTime(row.nextVisitProposalAt)}`
          : "",
    };
  };

  const mapAds = (bootstrapPayload) => {
    const projects = bootstrapPayload?.projects || [];
    const assets = bootstrapPayload?.marketing_assets || [];
    const projectById = new Map(
      projects.map((project) => [String(project.id), project]),
    );

    if (!assets.length) {
      return projects.map((project) => ({
        id: `project-${project.id}`,
        title: project.code || project.name || "Proyecto",
        line1: project.description || "Proyecto activo de Vertice360.",
        line2: project.name
          ? `Proyecto: ${project.name}`
          : "Disponible para consulta.",
        chips: project.tags || [],
        projectCode: project.code || "",
        whatsappPrefill: project.code || "",
        barrio: extractProjectBarrio(project?.name, project?.location_jsonb),
      }));
    }

    return assets.map((asset) => {
      const linkedProject = projectById.get(String(asset.project_id));
      const projectCode = asset.project_code || linkedProject?.code || "";
      return {
        id: String(asset.id),
        title:
          asset.title || asset.project_code || linkedProject?.code || "Anuncio",
        line1:
          asset.short_copy ||
          linkedProject?.description ||
          "Activo de campaña disponible en el orquestador.",
        line2: asset.project_name
          ? `Proyecto: ${asset.project_name}`
          : asset.channel
            ? `Canal: ${asset.channel}`
            : "",
        chips: Array.isArray(asset.chips) ? asset.chips : [],
        projectCode,
        whatsappPrefill: asset.whatsapp_prefill || projectCode,
        barrio: extractProjectBarrio(asset.project_name || linkedProject?.name, linkedProject?.location_jsonb),
      };
    });
  };

  const mapKpis = (rawKpis) => {
    const raw = rawKpis || {};
    return [
      { label: "Tickets totales", value: String(raw.tickets_total ?? 0) },
      { label: "Nuevos", value: String(raw.tickets_nuevo ?? 0) },
      {
        label: "En seguimiento",
        value: String(raw.tickets_en_seguimiento ?? 0),
      },
      {
        label: "Pend. visita",
        value: String(raw.tickets_pendiente_visita ?? 0),
      },
      {
        label: "Esperando conf.",
        value: String(raw.tickets_esperando_confirmacion ?? 0),
      },
      {
        label: "Visitas confirmadas",
        value: String(raw.tickets_visita_confirmada ?? 0),
      },
    ];
  };

  const getKpiStyle = (label) => {
    const l = String(label || "").toLowerCase();
    if (l.includes("totales"))
      return {
        bg: "bg-violet-50/50",
        border: "border-violet-100",
        text: "text-violet-600",
        icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
      };
    if (l.includes("nuevo"))
      return {
        bg: "bg-sky-50/50",
        border: "border-sky-100",
        text: "text-sky-600",
        icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><path d="M20 8v6"/><path d="M23 11h-6"/></svg>`,
      };
    if (l.includes("seguimiento"))
      return {
        bg: "bg-amber-50/50",
        border: "border-amber-100",
        text: "text-amber-600",
        icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
      };
    if (l.includes("pend"))
      return {
        bg: "bg-pink-50/50",
        border: "border-pink-100",
        text: "text-pink-600",
        icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
      };
    if (l.includes("esperando"))
      return {
        bg: "bg-rose-50/50",
        border: "border-rose-100",
        text: "text-rose-600",
        icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
      };
    if (l.includes("confirmadas"))
      return {
        bg: "bg-emerald-50/50",
        border: "border-emerald-100",
        text: "text-emerald-600",
        icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
      };
    return {
      bg: "bg-slate-50/50",
      border: "border-slate-100",
      text: "text-slate-600",
      icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 8 14"/><path d="M13 22H7"/><path d="M17 22h-6"/></svg>`,
    };
  };

  const mapConversationRow = (row) => {
    const ticketId = String(row?.ticket_id || "");
    return {
      id: ticketId || `ticket-${Math.random().toString(36).slice(2)}`,
      ticketId,
      leadId: row?.lead_id ? String(row.lead_id) : "",
      proyecto: row?.project_label || row?.project_code || row?.project_name || "General",
      cliente: row?.phone_e164 || "--",
      estado: row?.stage || "Nuevo",
      ultimoMensaje: row?.last_message_snippet || "Sin mensajes",
      createdAt: row?.created_at || null,
      lastActivityAt: row?.last_message_at || row?.last_activity_at || null,
      nextVisitProposalAt: null,
      visitAt: row?.visit_scheduled_at || null,
      aiResponded: false,
      raw: row,
    };
  };

  const mapMessageRole = (actor) => {
    const clean = String(actor || "").toLowerCase();
    if (clean === "client") return "Cliente";
    if (clean === "advisor") return "Asesor";
    if (clean === "supervisor") return "Supervisor";
    return "AI";
  };

  const mapMessages = (messages) => {
    return (messages || []).map((message) => ({
      id: String(message.id),
      role: mapMessageRole(message.actor),
      text: String(message.text || ""),
      timestamp: message.created_at,
      trace: `${mapMessageRole(message.actor)} • ${String(message.direction || "-").toUpperCase()}`,
    }));
  };

  const setRowProposalWindow = (ticketId, proposal) => {
    if (!ticketId) return;
    const nextOption =
      proposal?.option1 || proposal?.option2 || proposal?.option3 || null;
    if (!nextOption) return;

    conversations = conversations.map((row) =>
      row.ticketId === ticketId
        ? {
            ...row,
            nextVisitProposalAt: nextOption,
          }
        : row,
    );
  };

  const setRowVisitAt = (ticketId, visitAt) => {
    if (!ticketId || !visitAt) return;
    conversations = conversations.map((row) =>
      row.ticketId === ticketId
        ? {
            ...row,
            visitAt,
          }
        : row,
    );
  };

  const hasActiveProposal = (ticketId) =>
    Boolean(activeProposalByTicket[ticketId]?.id);
  const detailLoading = (ticketId) => Boolean(detailLoadingByTicket[ticketId]);
  const isAiHandled = (row) => Boolean(row.aiHandled || row.aiResponded);

  const getRowActions = (row) => {
    const estado = row.estado;
    const quickActions = [];

    if (isPendingVisit(estado)) {
      quickActions.push({ id: "visit", label: "Visita", tone: "primary" });
    } else if (isWaitingConfirmation(estado)) {
      quickActions.push({ id: "visit", label: "Visita", tone: "primary" });
      quickActions.push({
        id: "confirm",
        label: "Confirmar",
        tone: "success",
        disabled:
          !hasActiveProposal(row.ticketId) ||
          detailLoading(row.ticketId) ||
          isActionRunning,
      });
    } else if (isVisitConfirmed(estado)) {
      quickActions.push({
        id: "reschedule",
        label: "Reagendar",
        tone: "outline",
      });
    } else if (isGeneralFollowUp(estado)) {
      // Solo "Ver" en estados de seguimiento general.
    }

    return [
      ...quickActions.slice(0, 2),
      { id: "view", label: "Ver", tone: "ghost", disabled: false },
    ];
  };

  const resetUiState = () => {
    notice = "";
    errorMessage = "";
    modalOpen = false;
    detailModalOpen = false;
    selectedConversation = null;
    selectedLead = null;
    detailMessages = [];
    detailMessagesLoading = false;
  };

  const ensureTicketDetail = async (
    ticketId,
    { withMessages = false, force = false, silent = false } = {},
  ) => {
    const cleanTicketId = String(ticketId || "").trim();
    if (!cleanTicketId) return null;

    if (!force && detailByTicket[cleanTicketId]) {
      return detailByTicket[cleanTicketId];
    }

    detailLoadingByTicket = { ...detailLoadingByTicket, [cleanTicketId]: true };

    try {
      const payload = await ticketDetail({ ticketId: cleanTicketId });
      detailByTicket = {
        ...detailByTicket,
        [cleanTicketId]: payload,
      };
      activeProposalByTicket = {
        ...activeProposalByTicket,
        [cleanTicketId]: payload?.active_proposal || null,
      };
      setRowProposalWindow(cleanTicketId, payload?.active_proposal);
      setRowVisitAt(
        cleanTicketId,
        payload?.ticket?.visit_scheduled_at ||
          payload?.context?.visit_scheduled_at,
      );
      return payload;
    } catch (err) {
      if (!silent) {
        errorMessage =
          err?.message || "No se pudo cargar el detalle del ticket.";
      }
      return null;
    } finally {
      const next = { ...detailLoadingByTicket };
      delete next[cleanTicketId];
      detailLoadingByTicket = next;
    }
  };

  const preloadWaitingTicketDetails = async (rows) => {
    const waiting = (rows || []).filter(
      (row) => isWaitingConfirmation(row.estado) && row.ticketId,
    );
    if (!waiting.length) return;
    await Promise.allSettled(
      waiting.map((row) =>
        ensureTicketDetail(row.ticketId, {
          withMessages: false,
          force: false,
          silent: true,
        }),
      ),
    );
  };

  const loadBootstrap = async () => {
    if (bootstrapLoaded) return;
    isBootstrapping = true;
    errorMessage = "";
    whatsappPhoneError = "";
    try {
      const payload = await bootstrap({ cliente });
      ads = mapAds(payload);
      const digits = normalizePhoneDigits(payload?.whatsapp_demo_phone);
      if (digits) {
        demoWhatsAppPhone = digits;
      } else {
        demoWhatsAppPhone = "";
        whatsappPhoneError = WHATSAPP_PHONE_LOAD_ERROR;
      }
      bootstrapLoaded = true;
    } catch (err) {
      errorMessage = err?.message || "No se pudo cargar bootstrap.";
      demoWhatsAppPhone = "";
      whatsappPhoneError = WHATSAPP_PHONE_LOAD_ERROR;
    } finally {
      isBootstrapping = false;
    }
  };

  const loadDashboard = async ({ silent = false } = {}) => {
    if (!hasCliente()) return;

    isLoadingDashboard = true;
    if (!silent) {
      errorMessage = "";
    }

    try {
      const payload = await dashboard({ cliente });
      kpis = mapKpis(payload?.kpis);
      const rows = (payload?.tickets || []).map((row) =>
        mapConversationRow(row),
      );
      conversations = rows;
      await preloadWaitingTicketDetails(rows);
    } catch (err) {
      if (!silent) {
        errorMessage = err?.message || "No se pudo cargar dashboard.";
      }
    } finally {
      isLoadingDashboard = false;
      if (pendingDashboardRefresh) {
        pendingDashboardRefresh = false;
        void loadDashboard({ silent: true });
      }
    }
  };

  const refreshAfterAction = async (
    ticketId,
    { reloadDetail = false } = {},
  ) => {
    await loadDashboard({ silent: true });

    if (ticketId) {
      await ensureTicketDetail(ticketId, {
        withMessages: reloadDetail,
        force: true,
        silent: true,
      });
    }

    if (
      reloadDetail &&
      detailModalOpen &&
      selectedLead?.ticketId === ticketId
    ) {
      const detail = detailByTicket[ticketId];
      detailMessages = mapMessages(detail?.messages || []);
      const row = conversations.find((item) => item.ticketId === ticketId);
      if (row) {
        selectedLead = {
          id: row.ticketId,
          ticketId: row.ticketId,
          proyecto: row.proyecto,
          cliente: row.cliente,
          estado: row.estado,
        };
      }
    }
  };

  const useDemoCliente = () => {
    if (typeof window === "undefined") return;
    const demoCliente = "5491100000000";
    const url = new URL(window.location.href);
    url.searchParams.set("cliente", demoCliente);
    window.history.replaceState({}, "", url.toString());
    window.dispatchEvent(new PopStateEvent("popstate"));
  };

  const openVisitModal = async (row, mode = "proponer") => {
    selectedConversation = row;
    visitModalMode = mode;
    modalOpen = true;

    let activeProposal = activeProposalByTicket[row.ticketId] || null;
    if ((mode === "ver_propuesta" || mode === "reagendar") && !activeProposal) {
      const detail = await ensureTicketDetail(row.ticketId, {
        withMessages: false,
        force: true,
        silent: true,
      });
      activeProposal = detail?.active_proposal || null;
    }

    visitInitialValues = {
      advisor: "Asesor Demo",
      option1: toInputDateTime(activeProposal?.option1),
      option2: toInputDateTime(activeProposal?.option2),
      option3: toInputDateTime(activeProposal?.option3),
      message:
        activeProposal?.message_out ||
        (mode === "reagendar"
          ? "Te comparto nuevos horarios para reagendar la visita."
          : "Hola, te comparto opciones para coordinar una visita."),
    };
  };

  const closeVisitModal = () => {
    modalOpen = false;
  };

  const closeLeadDetail = () => {
    detailModalOpen = false;
  };

  const openLeadDetail = async (row) => {
    selectedLead = {
      id: row.ticketId,
      ticketId: row.ticketId,
      proyecto: row.proyecto,
      cliente: row.cliente,
      estado: row.estado,
    };
    detailModalOpen = true;
    detailMessages = [];
    detailMessagesLoading = true;

    try {
      const detail = await ensureTicketDetail(row.ticketId, {
        withMessages: true,
        force: true,
        silent: false,
      });
      detailMessages = mapMessages(detail?.messages || []);
    } finally {
      detailMessagesLoading = false;
    }
  };

  const sendVisitOptions = async (payload) => {
    if (!selectedConversation?.ticketId) return;

    isActionRunning = true;
    errorMessage = "";

    const body = {
      ticket_id: selectedConversation.ticketId,
      advisor_name: String(payload?.asesor || "").trim() || null,
      option1: toIsoOrNull(payload?.opcion1),
      option2: toIsoOrNull(payload?.opcion2),
      option3: toIsoOrNull(payload?.opcion3),
      message_out:
        String(payload?.mensaje || "").trim() ||
        "Mensaje enviado desde orquestador live.",
    };

    try {
      if (visitModalMode === "reagendar") {
        await rescheduleVisit(body);
        notice = `Reagenda enviada para ${payload?.cliente || "cliente"}.`;
      } else {
        await proposeVisit({
          ...body,
          mode: "propose",
        });
        notice = `Opciones enviadas para ${payload?.cliente || "cliente"}.`;
      }
      await refreshAfterAction(selectedConversation.ticketId, {
        reloadDetail: true,
      });
    } catch (err) {
      errorMessage =
        err?.message || "No se pudo enviar la propuesta de visita.";
      throw err;
    } finally {
      isActionRunning = false;
    }
  };

  const getFirstAvailableProposalOption = (proposal) => {
    if (proposal?.option1) return 1;
    if (proposal?.option2) return 2;
    if (proposal?.option3) return 3;
    return null;
  };

  const confirmActiveProposal = async (row) => {
    const ticketId = row?.ticketId;
    if (!ticketId) return;

    isActionRunning = true;
    errorMessage = "";

    try {
      const detail = await ensureTicketDetail(ticketId, {
        withMessages: false,
        force: true,
        silent: false,
      });
      const proposal = detail?.active_proposal;
      if (!proposal?.id) {
        throw new Error("No hay propuesta activa para confirmar.");
      }

      const confirmedOption = getFirstAvailableProposalOption(proposal);
      if (!confirmedOption) {
        throw new Error("La propuesta activa no tiene opciones válidas.");
      }

      await confirmVisit({
        proposal_id: proposal.id,
        confirmed_option: confirmedOption,
        confirmed_by: "advisor",
      });

      notice = "Visita confirmada correctamente.";
      await refreshAfterAction(ticketId, { reloadDetail: true });
    } catch (err) {
      errorMessage = err?.message || "No se pudo confirmar la visita.";
    } finally {
      isActionRunning = false;
    }
  };

  const handleSupervisorSend = async (payload) => {
    const ticketId = selectedLead?.ticketId;
    if (!ticketId) return;

    supervisorSending = true;
    errorMessage = "";

    try {
      await supervisorSend({
        ticket_id: ticketId,
        target: payload?.target,
        text: payload?.text,
      });
      notice = "Mensaje de supervisor enviado.";
      await refreshAfterAction(ticketId, { reloadDetail: true });
    } catch (err) {
      errorMessage =
        err?.message || "No se pudo enviar el mensaje del supervisor.";
      throw err;
    } finally {
      supervisorSending = false;
    }
  };

  const executeConversationAction = async (actionId, row) => {
    if (isActionRunning) return;

    if (actionId === "confirm") {
      await confirmActiveProposal(row);
      return;
    }

    if (actionId === "visit") {
      const mode = isWaitingConfirmation(row.estado)
        ? "ver_propuesta"
        : "proponer";
      await openVisitModal(row, mode);
      return;
    }

    if (actionId === "reschedule") {
      await openVisitModal(row, "reagendar");
      return;
    }

    if (actionId === "view") {
      await openLeadDetail(row);
    }
  };

  const handleClienteFromPage = async (nextCliente) => {
    const clean = String(nextCliente || "").trim();
    if (clean === cliente) return;

    cliente = clean;
    resetUiState();

    if (!hasCliente()) {
      conversations = [];
      kpis = [];
      return;
    }

    await loadDashboard();
  };

  onMount(() => {
    const sseManager = createSseManager(URL_SSE, {
      eventTypes: Array.from(SSE_REFRESH_EVENTS),
      onStatus: (connected) => {
        sseConnected = Boolean(connected);
      },
      onEvent: (evt) => {
        if (!shouldRefreshFromSseEvent(evt)) return;
        scheduleDashboardRefresh();
      },
    });
    sseManager.connect();

    const fromUrl =
      typeof window !== "undefined"
        ? String(new URLSearchParams(window.location.search).get("cliente") || "").trim()
        : "";
    if (fromUrl) {
      cliente = fromUrl;
    }

    const fromPage = String(cliente || "").trim();
    if (fromPage) {
      cliente = fromPage;
    }

    const onClienteEvent = (event) => {
      void handleClienteFromPage(event?.detail?.cliente);
    };

    const onResetUi = () => {
      resetUiState();
      conversations = [];
      kpis = [];
    };

    window.addEventListener("orquestador-live:cliente", onClienteEvent);
    window.addEventListener("orquestador-live:reset-ui", onResetUi);

    void (async () => {
      await loadBootstrap();
      if (hasCliente()) {
        await loadDashboard();
      }
    })();

    return () => {
      sseManager.disconnect();
      if (refreshTimer) {
        clearTimeout(refreshTimer);
        refreshTimer = null;
      }
      window.removeEventListener("orquestador-live:cliente", onClienteEvent);
      window.removeEventListener("orquestador-live:reset-ui", onResetUi);
    };
  });
</script>

<div class="mx-0 md:mx-auto w-full md:max-w-7xl md:space-y-6 space-y-4">
  <header
    class="sticky top-0 md:top-4 z-50 backdrop-blur-xl bg-emerald-800 md:bg-white/75 border-b
    md:border border-slate-200/50
    shadow-sm shadow-slate-200/50 rounded-none md:rounded-3xl -my-8 md:-my-0 -mx-4 md:mx-0 px-4
    py-3 md:p-4 mb-0 md:mb-6 transition-all"
  >
    <div class="flex items-center justify-between gap-4">
      <div class="min-w-0 flex items-center gap-3">
        <div
          class="hidden md:flex h-10 w-10 md:h-12 md:w-12 items-center justify-center
          rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-700 text-white shadow-md text-sm md:text-base font-bold shrink-0"
        >
          V
        </div>
        <div class="min-w-0">
          <h1
            class="text-lg md:text-xl font-bold text-white md:text-slate-900 leading-tight truncate"
          >
            Orquestador
          </h1>
          <p
            class="text-[11px] md:text-[13px] text-slate-300 md:text-slate-500 font-medium truncate flex items-center gap-1 mt-0.5"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="text-slate-300 md:text-slate-400"
              ><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" /><circle
                cx="12"
                cy="7"
                r="4"
              /></svg
            >
            Cliente activo:
            <span class="text-slate-100 md:text-slate-800 font-semibold"
              >{normalizeClienteDisplay(cliente) || "Sin cliente"}</span
            >
          </p>
        </div>
      </div>
      <div class="flex items-center gap-1 md:gap-3 shrink-0">
        <span
          class="inline-flex items-center gap-1.5 bg-teal-50 border border-teal-200
          text-teal-700 font-bold uppercase tracking-wider rounded-full
          px-2 py-1 md:px-3 md:py-1.5 text-[9px] md:text-xs shadow-sm"
        >
          <div
            class={`w-1.5 h-1.5 rounded-full animate-pulse ${sseConnected ? "bg-teal-500" : "bg-amber-500"}`}
          ></div>
          {sseConnected ? "Live" : "Reconectando"}
        </span>
        <a
          href="/demo/vertice360-orquestador/"
          class="flex h-5 w-5 md:h-11 md:w-11 items-center justify-center md:bg-white md:border
          md:border-slate-200 md:shadow-sm text-slate-100
          md:text-slate-700 hover:bg-slate-50 hover:text-slate-900 hover:shadow transition-all
          rounded-full p-0 shrink-0"
          title="Volver"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </a>
      </div>
    </div>
  </header>

  {#if !hasCliente()}
    <div
      class="border border-amber-200 bg-amber-50/50 rounded-3xl p-4 md:p-6 flex flex-col md:flex-row items-center gap-4 transition-all animate-in fade-in slide-in-from-top-4 duration-500"
    >
      <div
        class="h-12 w-12 rounded-2xl bg-white shadow-sm flex items-center justify-center text-amber-500 shrink-0 border border-amber-100"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path
            d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"
          />
          <path d="M12 9v4" />
          <path d="M12 17h.01" />
        </svg>
      </div>
      <div class="flex-1 text-center md:text-left">
        <h3 class="text-amber-900 font-bold text-base leading-tight">
          Configuración necesaria
        </h3>
        <p class="text-amber-700/80 text-sm mt-0.5">
          No se detectó un <code>cliente</code> en la URL. Activá el modo demo para
          explorar las funcionalidades.
        </p>
      </div>
      <button
        type="button"
        class="btn bg-amber-500 hover:bg-amber-600 border-none text-white rounded-2xl px-6 min-h-[44px] h-[44px] shadow-sm shadow-amber-200/50"
        onclick={useDemoCliente}
      >
        Usar cliente demo
      </button>
    </div>
  {/if}

  {#if errorMessage}
    <div
      class="border border-rose-200 bg-rose-50/70 rounded-3xl p-4 flex items-center gap-3 transition-all animate-in fade-in zoom-in duration-300 shadow-sm shadow-rose-100/20"
    >
      <div
        class="h-8 w-8 rounded-xl bg-rose-100 flex items-center justify-center text-rose-600 shrink-0"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12"
           /><line x1="12" y1="16" x2="12.01" y2="16" /></svg
        >
      </div>
      <span class="text-rose-800 text-sm font-medium">{errorMessage}</span>
    </div>
  {/if}

  {#if notice}
    <div
      class="border border-blue-200 bg-blue-50/50 rounded-3xl p-4 flex items-center gap-3 transition-all animate-in fade-in zoom-in duration-300 shadow-sm shadow-blue-100/20"
    >
      <div
        class="h-8 w-8 rounded-xl bg-blue-100 flex items-center justify-center text-blue-600 shrink-0"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"
          ><circle cx="12" cy="12" r="10" /><line
            x1="12"
            y1="16"
            x2="12"
            y2="12"
          /><line x1="12" y1="8" x2="12.01" y2="8" /></svg
        >
      </div>
      <span class="text-blue-800 text-sm font-medium">{notice}</span>
    </div>
  {/if}

  <section class="mb-4 md:-mt-2">
    <div class="p-2">
      <h2
        class="text-lg md:text-2xl font-bold text-slate-700 flex items-center gap-2"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="text-emerald-600"
          ><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline
            points="7 10 12 15 17 10"
          /><line x1="12" x2="12" y1="15" y2="3" /></svg
        >
        Ejemplos de publicidad
      </h2>
      <p class="mt-2 text-sm text-slate-600 max-w-2xl leading-relaxed">
        Elegí un proyecto y abrí WhatsApp con el código listo para consultar.
        Vas a ver la conversación y su estado reflejados automáticamente en el
        Orquestador en tiempo real.
      </p>
    </div>

    {#if whatsappPhoneError}
      <div
        class="mb-4 border border-amber-200 bg-amber-50/50 rounded-2xl p-3 text-amber-800 text-sm"
      >
        {whatsappPhoneError}
      </div>
    {/if}

    {#if isBootstrapping}
      <div
        class="mb-4 border border-sky-200 bg-sky-50/50 rounded-2xl p-3 text-sky-800 text-sm"
      >
        Cargando campañas...
      </div>
    {:else}
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-6">
        {#each ads as ad, i}
          <article
            class="group relative bg-white flex flex-col w-full border border-slate-200/50 rounded-2xl
            shadow-sm hover:shadow-xl hover:shadow-emerald-900/5 hover:border-emerald-200 transition-all
            duration-500 hover:-translate-y-1 overflow-hidden"
          >
            <div
              class="relative h-40 w-full overflow-hidden shrink-0 bg-slate-100"
            >
              <div
                class="absolute inset-0 bg-gradient-to-t from-slate-900/60 via-transparent to-transparent z-10"
              ></div>
              <img
                src={`/depto${i + 1}.jpg`}
                alt={ad.title}
                class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                loading="lazy"
              />
              <div
                class="absolute bottom-4 left-4 right-4 z-20 flex justify-between items-end"
              >
                <h3
                  class="text-sm md:text-base font-bold text-white leading-tight drop-shadow-md"
                >
                  {ad.title}
                </h3>
              </div>
            </div>

            <div class="p-4 gap-4 flex flex-col flex-1 bg-white relative z-20">
              <div class="flex flex-col gap-2 flex-1">
                <div class="space-y-1">
                  <p class="text-sm text-slate-600 font-medium leading-relaxed">
                    {ad.line1}
                  </p>
                  <p class="text-sm text-slate-500 leading-relaxed font-medium">
                    {ad.line2}
                  </p>
                </div>
              </div>

              <div class="flex flex-col gap-3 pt-4 border-t border-slate-100">
                <div class="flex flex-wrap gap-1">
                  {#each ad.chips || [] as chip}
                    <span
                      class="inline-flex items-center px-2 py-1 rounded-lg bg-slate-50 text-slate-600 text-[11px] font-semibold border border-slate-200/80"
                    >
                      {chip}
                    </span>
                  {/each}
                </div>

                <a
                  href={getAdWhatsAppUrl(ad) || undefined}
                  target={getAdWhatsAppUrl(ad) ? "_blank" : undefined}
                  rel={getAdWhatsAppUrl(ad) ? "noreferrer noopener" : undefined}
                  aria-disabled={!getAdWhatsAppUrl(ad)}
                  tabindex={getAdWhatsAppUrl(ad) ? undefined : "-1"}
                  class={`btn-primary md:h-11 h-10 shrink-0 flex items-center justify-center gap-2 ${
                    getAdWhatsAppUrl(ad)
                      ? ""
                      : "pointer-events-none opacity-60 grayscale"
                  }`}
                >
                  <svg
                    xmlns={URL_SVG_XMLNS}
                    viewBox="0 0 24 24"
                    class="h-5 w-5 fill-current"
                    aria-hidden="true"
                  >
                    <path
                      d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"
                    />
                  </svg>
                  <span>Enviar WhatsApp</span>
                </a>
              </div>
            </div>
          </article>
        {/each}
      </div>
    {/if}
  </section>

  <section class="card-primary">
    <div class="card-body p-4 md:p-5">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg md:text-2xl font-bold text-slate-700 flex-1">
          Resumen de actividad
        </h2>
        <span
          class="text-[10px] font-bold uppercase tracking-wider text-slate-500 bg-slate-100 px-2
          py-0.5 rounded-full"
        >
          En tiempo real
        </span>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {#each kpis as kpi}
          {@const style = getKpiStyle(kpi.label)}
          <div
            class={`flex flex-col p-4 rounded-2xl border ${style.bg} ${style.border} transition-all hover:shadow-sm group`}
          >
            <div class="flex items-center justify-between mb-2">
              <div
                class={`h-8 w-8 rounded-xl flex items-center justify-center bg-white shadow-sm border ${style.border} ${style.text}`}
              >
                <div class="h-4 w-4">
                  {@html style.icon}
                </div>
              </div>
            </div>
            <p
              class="text-[10px] uppercase font-bold tracking-widest text-slate-400 group-hover:text-slate-500 transition-colors"
            >
              {kpi.label}
            </p>
            <p class="mt-1 text-xl sm:text-2xl font-bold text-slate-700">
              {kpi.value}
            </p>
          </div>
        {/each}
      </div>
    </div>
  </section>

  <section class="card-primary">
    <div class="card-body p-4 md:p-5 gap-3">
      <div class="flex items-center justify-between">
        <h2 class="text-lg md:text-2xl font-bold text-slate-700">
          Conversaciones y estado
        </h2>
        {#if isLoadingDashboard}
          <span class="loading loading-spinner loading-sm"></span>
        {/if}
      </div>

      <div class="md:hidden space-y-3">
        {#each conversations as row, i}
          {#if i === 0 || row.proyecto !== conversations[i - 1].proyecto}
            <div class="pt-4 pb-1">
              <span
                class="text-[10px] font-bold uppercase tracking-widest text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded"
              >
                {row.proyecto}
              </span>
            </div>
          {/if}
          <article
            class="card-primary p-3 space-y-2 border border-slate-100 shadow-sm"
          >
            <div class="flex items-start justify-between gap-2">
              <div>
                <p class="text-xs text-slate-500">{row.cliente}</p>
              </div>
              <div class="flex items-center gap-2">
                <span
                  class={`badge badge-sm whitespace-nowrap ${estadoBadge(row.estado)}`}
                >
                  {estadoLabel(row.estado)}
                </span>
                {#if isAiHandled(row)}
                  <span class="badge badge-outline badge-xs whitespace-nowrap"
                    >AI</span
                  >
                {/if}
              </div>
            </div>
            <p
              class="text-sm text-slate-700 break-words overflow-hidden text-ellipsis [display:-webkit-box] [-webkit-line-clamp:2] [-webkit-box-orient:vertical] leading-5"
            >
              {row.ultimoMensaje}
            </p>
            <div
              class="flex items-center justify-between pt-2 border-t border-slate-50"
            >
              <div class="min-w-0">
                <p class="text-[10px] text-slate-400 font-medium">
                  Última actividad
                </p>
                <p class="text-[11px] text-slate-600 truncate">
                  {getConversationDateInfo(row).primary}
                </p>
              </div>
              <div class="flex gap-1.5">
                {#if getRowActions(row).length === 0}
                  <span class="text-[10px] text-slate-400 italic"
                    >Sin acciones</span
                  >
                {:else}
                  {#each getRowActions(row) as action}
                    <button
                      type="button"
                      class={`${actionClass(action.tone)} ${action.disabled ? "opacity-40 cursor-not-allowed" : ""}`}
                      aria-label={actionLabel(action.id)}
                      title={action.id === "confirm" &&
                      !hasActiveProposal(row.ticketId)
                        ? "No hay propuesta activa para confirmar"
                        : actionLabel(action.id)}
                      onclick={() => executeConversationAction(action.id, row)}
                      disabled={Boolean(action.disabled)}
                    >
                      {@html actionIcon(action.id)}
                    </button>
                  {/each}
                {/if}
              </div>
            </div>
          </article>
        {/each}
      </div>

      <div class="hidden md:block rounded-2xl border border-base-300">
        <div class="max-h-[480px] overflow-y-auto overflow-x-auto pr-1 pb-3">
          <table class="table table-zebra table-sm">
            <thead class="sticky top-0 z-20 bg-base-100">
              <tr>
                <th class="p-3 whitespace-nowrap">Proyecto</th>
                <th class="p-3 whitespace-nowrap">Cliente</th>
                <th class="p-3 whitespace-nowrap">Estado</th>
                <th class="p-3 whitespace-nowrap">Fecha/Hora</th>
                <th class="p-3">Último mensaje</th>
                <th class="p-3 whitespace-nowrap text-right">Acción</th>
              </tr>
            </thead>
            <tbody>
              {#each conversations as row, i}
                {#if i === 0 || row.proyecto !== conversations[i - 1].proyecto}
                  <tr class="bg-slate-50/80">
                    <td colspan="6" class="px-3 py-1.5">
                      <span
                        class="text-[10px] font-bold uppercase tracking-widest text-emerald-800"
                      >
                        PROYECTO: {row.proyecto}
                      </span>
                    </td>
                  </tr>
                {/if}
                <tr class="group hover:bg-slate-50/50 transition-colors">
                  <td class="p-3 font-medium text-slate-400 align-top text-xs">
                    {row.proyecto}
                  </td>
                  <td class="p-3 whitespace-nowrap align-top">{row.cliente}</td>
                  <td class="px-3 py-3 align-top">
                    <div class="flex items-center gap-2">
                      <span
                        class={`badge badge-sm whitespace-nowrap ${estadoBadge(row.estado)}`}
                      >
                        {estadoLabel(row.estado)}
                      </span>
                      {#if isAiHandled(row)}
                        <span
                          class="badge badge-outline badge-xs whitespace-nowrap"
                          >AI</span
                        >
                      {/if}
                    </div>
                  </td>
                  <td class="p-3 align-top">
                    <p
                      class="text-sm text-slate-800 leading-5 whitespace-nowrap"
                    >
                      {getConversationDateInfo(row).primary}
                    </p>
                    <p
                      class="text-xs text-slate-500 leading-5 min-h-5 whitespace-nowrap"
                    >
                      {getConversationDateInfo(row).secondary || "\u00A0"}
                    </p>
                  </td>
                  <td class="p-3 align-top">
                    <p
                      class="text-sm text-slate-700 break-words overflow-hidden text-ellipsis
                       [display:-webkit-box] [-webkit-line-clamp:2] [-webkit-box-orient:vertical]
                       leading-5"
                    >
                      {row.ultimoMensaje}
                    </p>
                  </td>
                  <td class="p-3 align-top text-right">
                    {#if getRowActions(row).length > 0}
                      <div class="flex justify-end gap-2 flex-wrap">
                        {#each getRowActions(row) as action}
                          <button
                            type="button"
                            class={`${actionClass(action.tone)} ${action.disabled ? "opacity-40 cursor-not-allowed" : ""}`}
                            aria-label={actionLabel(action.id)}
                            title={action.id === "confirm" &&
                            !hasActiveProposal(row.ticketId)
                              ? "No hay propuesta activa para confirmar"
                              : actionLabel(action.id)}
                            onclick={() =>
                              executeConversationAction(action.id, row)}
                            disabled={Boolean(action.disabled)}
                          >
                            {@html actionIcon(action.id)}
                          </button>
                        {/each}
                      </div>
                    {:else}
                      <span class="text-xs text-slate-500">Sin acciones</span>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>
</div>

<VisitProposalModal
  open={modalOpen}
  cliente={selectedConversation?.cliente || cliente}
  mode={visitModalMode}
  initialAdvisor={visitInitialValues.advisor}
  initialOption1={visitInitialValues.option1}
  initialOption2={visitInitialValues.option2}
  initialOption3={visitInitialValues.option3}
  initialMessage={visitInitialValues.message}
  onClose={closeVisitModal}
  onSubmit={sendVisitOptions}
/>

<LeadDetailModal
  open={detailModalOpen}
  lead={selectedLead}
  messages={detailMessages}
  loadingMessages={detailMessagesLoading}
  {supervisorSending}
  onSupervisorSend={handleSupervisorSend}
  onClose={closeLeadDetail}
/>
