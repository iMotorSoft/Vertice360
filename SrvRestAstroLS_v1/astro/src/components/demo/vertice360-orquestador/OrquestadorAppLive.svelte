<script>
  import { onMount } from "svelte";
  import { URL_SVG_XMLNS, URL_WA_ME } from "../../global.js";

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

  let isBootstrapping = $state(false);
  let isLoadingDashboard = $state(false);
  let isActionRunning = $state(false);

  let demoWhatsAppPhone = $state("4526325250");
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

  const normalizeClienteDisplay = (value) => {
    const compact = String(value || "").replace(/[\s-]+/g, "");
    if (!compact) return "";
    const withoutPlus = compact.replace(/^\++/, "");
    if (!withoutPlus) return "";
    return `+${withoutPlus}`;
  };

  const hasCliente = () => Boolean(normalizeClienteDisplay(cliente));

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

  const buildWhatsAppUrl = (projectCode) => {
    const payload = String(projectCode || "").trim() || "VERTICE360";
    return `${URL_WA_ME}/${demoWhatsAppPhone}/?text=${encodeURIComponent(payload)}`;
  };

  const estadoLabel = (estado) => {
    if (estado === STAGE_WAITING_CONFIRMATION) return "Esperando conf.";
    return estado;
  };

  const estadoBadge = (estado) => {
    if (estado === "Nuevo") return "badge-info";
    if (estado === "En seguimiento") return "badge-warning";
    if (estado === "Pendiente de visita") return "badge-primary";
    if (estado === STAGE_WAITING_CONFIRMATION) return "badge-accent";
    if (estado === "Visita confirmada") return "badge-success";
    return "badge-ghost";
  };

  const isWaitingConfirmation = (estado) =>
    estado === STAGE_WAITING_CONFIRMATION || estado === "Esperando conf.";
  const isVisitConfirmed = (estado) => estado === "Visita confirmada";
  const isPendingVisit = (estado) => estado === "Pendiente de visita";
  const isGeneralFollowUp = (estado) =>
    estado === "Nuevo" || estado === "En seguimiento" || estado === "Esperando respuesta";

  const actionClass = (tone) => {
    const base = "btn btn-sm min-h-11 md:btn-xs md:min-h-[28px] whitespace-nowrap";
    if (tone === "primary") return `${base} btn-primary`;
    if (tone === "success") return `${base} btn-success`;
    if (tone === "outline") return `${base} btn-outline`;
    return `${base} btn-ghost`;
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
      primary: activityAt ? `Último: ${formatDateTime(activityAt)}` : "Sin actividad",
      secondary:
        row.estado === STAGE_WAITING_CONFIRMATION && row.nextVisitProposalAt
          ? `Propuesta: ${formatDateTime(row.nextVisitProposalAt)}`
          : "",
    };
  };

  const mapAds = (bootstrapPayload) => {
    const projects = bootstrapPayload?.projects || [];
    const assets = bootstrapPayload?.marketing_assets || [];
    const projectById = new Map(projects.map((project) => [String(project.id), project]));

    if (!assets.length) {
      return projects.map((project) => ({
        id: `project-${project.id}`,
        title: project.code || project.name || "Proyecto",
        line1: project.description || "Proyecto activo de Vertice360.",
        line2: project.name ? `Proyecto: ${project.name}` : "Disponible para consulta.",
        chips: project.tags || [],
        projectCode: project.code || "",
        whatsappPrefill: project.code || "",
      }));
    }

    return assets.map((asset) => {
      const linkedProject = projectById.get(String(asset.project_id));
      return {
        id: String(asset.id),
        title: asset.title || asset.project_code || linkedProject?.code || "Anuncio",
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
        projectCode: asset.project_code || linkedProject?.code || "",
        whatsappPrefill: asset.whatsapp_prefill || asset.project_code || linkedProject?.code || "",
      };
    });
  };

  const mapKpis = (rawKpis) => {
    const raw = rawKpis || {};
    return [
      { label: "Tickets totales", value: String(raw.tickets_total ?? 0) },
      { label: "Nuevos", value: String(raw.tickets_nuevo ?? 0) },
      { label: "En seguimiento", value: String(raw.tickets_en_seguimiento ?? 0) },
      { label: "Pend. visita", value: String(raw.tickets_pendiente_visita ?? 0) },
      { label: "Esperando conf.", value: String(raw.tickets_esperando_confirmacion ?? 0) },
      { label: "Visitas confirmadas", value: String(raw.tickets_visita_confirmada ?? 0) },
    ];
  };

  const mapConversationRow = (row) => {
    const ticketId = String(row?.ticket_id || "");
    return {
      id: ticketId || `ticket-${Math.random().toString(36).slice(2)}`,
      ticketId,
      leadId: row?.lead_id ? String(row.lead_id) : "",
      proyecto: row?.project_code || row?.project_name || "Sin proyecto",
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
    const nextOption = proposal?.option1 || proposal?.option2 || proposal?.option3 || null;
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

  const hasActiveProposal = (ticketId) => Boolean(activeProposalByTicket[ticketId]?.id);
  const detailLoading = (ticketId) => Boolean(detailLoadingByTicket[ticketId]);

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
        disabled: !hasActiveProposal(row.ticketId) || detailLoading(row.ticketId) || isActionRunning,
      });
    } else if (isVisitConfirmed(estado)) {
      quickActions.push({ id: "reschedule", label: "Reagendar", tone: "outline" });
    } else if (isGeneralFollowUp(estado)) {
      // Solo "Ver" en estados de seguimiento general.
    }

    return [...quickActions.slice(0, 2), { id: "view", label: "Ver", tone: "ghost", disabled: false }];
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

  const ensureTicketDetail = async (ticketId, { withMessages = false, force = false, silent = false } = {}) => {
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
      setRowVisitAt(cleanTicketId, payload?.ticket?.visit_scheduled_at || payload?.context?.visit_scheduled_at);
      return payload;
    } catch (err) {
      if (!silent) {
        errorMessage = err?.message || "No se pudo cargar el detalle del ticket.";
      }
      return null;
    } finally {
      const next = { ...detailLoadingByTicket };
      delete next[cleanTicketId];
      detailLoadingByTicket = next;
    }
  };

  const preloadWaitingTicketDetails = async (rows) => {
    const waiting = (rows || []).filter((row) => isWaitingConfirmation(row.estado) && row.ticketId);
    if (!waiting.length) return;
    await Promise.allSettled(
      waiting.map((row) => ensureTicketDetail(row.ticketId, { withMessages: false, force: false, silent: true })),
    );
  };

  const loadBootstrap = async () => {
    if (bootstrapLoaded) return;
    isBootstrapping = true;
    errorMessage = "";
    try {
      const payload = await bootstrap({ cliente });
      ads = mapAds(payload);
      const digits = String(payload?.whatsapp_demo_phone || "").replace(/\D+/g, "");
      if (digits) {
        demoWhatsAppPhone = digits;
      }
      bootstrapLoaded = true;
    } catch (err) {
      errorMessage = err?.message || "No se pudo cargar bootstrap.";
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
      const rows = (payload?.tickets || []).map((row) => mapConversationRow(row));
      conversations = rows;
      await preloadWaitingTicketDetails(rows);
    } catch (err) {
      if (!silent) {
        errorMessage = err?.message || "No se pudo cargar dashboard.";
      }
    } finally {
      isLoadingDashboard = false;
    }
  };

  const refreshAfterAction = async (ticketId, { reloadDetail = false } = {}) => {
    await loadDashboard({ silent: true });

    if (ticketId) {
      await ensureTicketDetail(ticketId, { withMessages: reloadDetail, force: true, silent: true });
    }

    if (reloadDetail && detailModalOpen && selectedLead?.ticketId === ticketId) {
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
      const detail = await ensureTicketDetail(row.ticketId, { withMessages: false, force: true, silent: true });
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
      message_out: String(payload?.mensaje || "").trim() || "Mensaje enviado desde orquestador live.",
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
      await refreshAfterAction(selectedConversation.ticketId, { reloadDetail: true });
    } catch (err) {
      errorMessage = err?.message || "No se pudo enviar la propuesta de visita.";
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
      const detail = await ensureTicketDetail(ticketId, { withMessages: false, force: true, silent: false });
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
      errorMessage = err?.message || "No se pudo enviar el mensaje del supervisor.";
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
      const mode = isWaitingConfirmation(row.estado) ? "ver_propuesta" : "proponer";
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
      window.removeEventListener("orquestador-live:cliente", onClienteEvent);
      window.removeEventListener("orquestador-live:reset-ui", onResetUi);
    };
  });
</script>

<div class="mx-auto w-full max-w-7xl space-y-4 px-4 sm:px-5 lg:px-6">
  <header class="card rounded-xl border border-base-300 bg-base-100 shadow-md">
    <div class="card-body p-5 md:p-6">
      <div class="flex gap-4">
        <div class="w-1.5 bg-primary rounded-full self-stretch"></div>
        <div class="min-w-0 flex-1">
          <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div class="min-w-0 flex items-start gap-3">
              <div
                class="flex h-10 w-10 md:h-12 md:w-12 items-center justify-center rounded-xl bg-primary/10 text-primary text-sm md:text-base font-bold"
              >
                V
              </div>
              <div class="min-w-0">
                <h1 class="text-2xl font-bold leading-tight text-slate-900">Orquestador</h1>
                <p class="mt-1 text-sm text-base-content/60 break-all sm:break-normal">
                  Cliente activo: {normalizeClienteDisplay(cliente) || "Sin cliente"}
                </p>
              </div>
            </div>
            <div class="flex items-center justify-between gap-2 sm:justify-end">
              <span class="badge badge-primary badge-outline">LIVE</span>
              <a
                href="/demo/vertice360-orquestador/"
                class="btn btn-ghost btn-sm min-h-11"
              >
                <span aria-hidden="true">←</span>
                Volver
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </header>

  {#if !hasCliente()}
    <div class="alert alert-warning mb-4">
      <span>Falta el parámetro <code>cliente</code> en la URL.</span>
      <button
        type="button"
        class="btn btn-sm btn-warning min-h-11"
        onclick={useDemoCliente}>Usar cliente demo</button
      >
    </div>
  {/if}

  {#if errorMessage}
    <div class="alert alert-error">
      <span>{errorMessage}</span>
    </div>
  {/if}

  {#if notice}
    <div class="alert alert-info">
      <span>{notice}</span>
    </div>
  {/if}

  <section class="card border border-base-300 bg-base-100 shadow-sm">
    <div class="card-body p-4 md:p-5">
      <h2 class="text-base md:text-lg font-semibold text-slate-900">
        Ejemplos de publicidad
      </h2>
      <p class="mt-1 text-sm text-slate-700">
        Elegí un proyecto y abrí WhatsApp con el código listo para consultar.
      </p>
      <p class="text-xs text-slate-500">
        Vas a ver la conversación y su estado reflejados en el Orquestador.
      </p>

      {#if isBootstrapping}
        <div class="mt-4 alert alert-info">
          <span>Cargando campañas...</span>
        </div>
      {:else}
        <div class="mt-3 grid gap-3 md:grid-cols-3">
          {#each ads as ad}
            <article class="card border border-base-300 bg-base-100">
              <div class="h-28 rounded-t-2xl bg-slate-200"></div>
              <div class="card-body p-4 gap-2">
                <h3 class="font-semibold text-slate-900">{ad.title}</h3>
                <div class="space-y-1">
                  <p class="text-sm text-slate-600 break-words">{ad.line1}</p>
                  <p class="text-sm text-slate-600 break-words">{ad.line2}</p>
                </div>
                <div class="flex flex-wrap gap-1">
                  {#each ad.chips || [] as chip}
                    <span class="badge badge-outline badge-sm">{chip}</span>
                  {/each}
                </div>
                <a
                  href={buildWhatsAppUrl(ad.whatsappPrefill || ad.projectCode || ad.title)}
                  target="_blank"
                  rel="noreferrer"
                  class="btn btn-sm min-h-11 border-0 bg-[#25D366] text-white hover:bg-[#1EBE5D] inline-flex items-center gap-2"
                >
                  <svg
                    xmlns={URL_SVG_XMLNS}
                    viewBox="0 0 32 32"
                    class="h-4 w-4 fill-current"
                    aria-hidden="true"
                  >
                    <path
                      d="M19.1 17.2c-.3-.2-1.7-.8-1.9-.9-.3-.1-.5-.2-.8.2-.2.3-.9.9-1.1 1.1-.2.2-.4.2-.7.1-.3-.2-1.3-.5-2.5-1.6-.9-.8-1.5-1.8-1.7-2.1-.2-.3 0-.5.1-.7.1-.1.3-.3.4-.5.1-.1.2-.3.3-.5.1-.2 0-.4 0-.5 0-.1-.8-1.9-1.1-2.6-.3-.7-.6-.6-.8-.6h-.7c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.3 0 1.3 1 2.6 1.1 2.8.1.2 1.9 3 4.7 4.2 2.8 1.2 2.8.8 3.4.8.6 0 1.9-.8 2.2-1.5.3-.8.3-1.4.2-1.5-.1-.2-.3-.2-.6-.4z"
                    ></path>
                    <path
                      d="M16 3C8.8 3 3 8.8 3 16c0 2.3.6 4.5 1.8 6.4L3 29l6.8-1.8c1.8 1 3.9 1.5 6.2 1.5 7.2 0 13-5.8 13-13S23.2 3 16 3zm0 23.4c-2 0-4-.5-5.7-1.5l-.4-.2-4 1 1.1-3.9-.3-.4c-1.1-1.7-1.6-3.7-1.6-5.8 0-5.9 4.9-10.8 10.9-10.8s10.8 4.8 10.8 10.8S21.9 26.4 16 26.4z"
                    ></path>
                  </svg>
                  Enviar WhatsApp
                </a>
              </div>
            </article>
          {/each}
        </div>
      {/if}
    </div>
  </section>

  <section class="card border border-base-300 bg-base-100 shadow-sm">
    <div class="card-body p-4 md:p-5">
      <h2 class="text-base md:text-lg font-semibold text-slate-900">
        Actividad en tiempo real
      </h2>
      <div class="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3">
        {#each kpis as kpi}
          <div class="rounded-2xl border border-base-300 bg-base-100 p-3">
            <p class="text-xs uppercase tracking-wide text-slate-500">{kpi.label}</p>
            <p class="mt-1 text-2xl font-bold text-slate-900">{kpi.value}</p>
          </div>
        {/each}
      </div>
    </div>
  </section>

  <section class="card border border-base-300 bg-base-100 shadow-sm">
    <div class="card-body p-4 md:p-5 gap-3">
      <div class="flex items-center justify-between gap-3">
        <h2 class="text-base md:text-lg font-semibold text-slate-900">Conversaciones y estado</h2>
        {#if isLoadingDashboard}
          <span class="loading loading-spinner loading-sm"></span>
        {/if}
      </div>

      <div class="md:hidden space-y-3">
        {#each conversations as row}
          <article class="rounded-2xl border border-base-300 bg-base-100 p-3 space-y-2">
            <div class="flex items-start justify-between gap-2">
              <div>
                <p class="text-sm font-semibold text-slate-900">{row.proyecto}</p>
                <p class="text-xs text-slate-500">{row.cliente}</p>
              </div>
              <div class="flex items-center gap-2">
                <span class={`badge badge-sm whitespace-nowrap ${estadoBadge(row.estado)}`}>
                  {estadoLabel(row.estado)}
                </span>
              </div>
            </div>
            <p
              class="text-sm text-slate-700 break-words overflow-hidden text-ellipsis [display:-webkit-box] [-webkit-line-clamp:2] [-webkit-box-orient:vertical] leading-5"
            >
              {row.ultimoMensaje}
            </p>
            <div class="space-y-1">
              <p class="text-xs text-slate-600">{getConversationDateInfo(row).primary}</p>
              <p class="text-xs text-slate-500 min-h-4">{getConversationDateInfo(row).secondary || "\u00A0"}</p>
            </div>
            <div class="flex flex-col gap-2">
              {#if getRowActions(row).length === 0}
                <p class="text-xs text-slate-500">Sin acciones disponibles.</p>
              {:else}
                {#each getRowActions(row) as action}
                  <button
                    type="button"
                    class={actionClass(action.tone)}
                    onclick={() => executeConversationAction(action.id, row)}
                    disabled={Boolean(action.disabled)}
                    title={action.id === "confirm" && !hasActiveProposal(row.ticketId)
                      ? "No hay propuesta activa para confirmar"
                      : ""}
                  >
                    {action.label}
                  </button>
                {/each}
              {/if}
            </div>
          </article>
        {/each}
      </div>

      <div class="hidden md:block rounded-2xl border border-base-300">
        <div class="max-h-[480px] overflow-y-auto overflow-x-auto pr-1 pb-3">
          <table class="table table-zebra table-sm">
            <thead class="sticky top-0 z-20 bg-base-100">
              <tr>
                <th class="w-[140px] px-3 py-3">Proyecto</th>
                <th class="w-[170px] px-3 py-3">Cliente</th>
                <th class="w-[190px] px-3 py-3">Estado</th>
                <th class="w-[180px] px-3 py-3">Fecha/Hora</th>
                <th class="w-[280px] px-3 py-3">Último mensaje</th>
                <th class="w-[220px] min-w-[220px] px-3 py-3 text-right">Acción</th>
              </tr>
            </thead>
            <tbody>
              {#each conversations as row}
                <tr>
                  <td class="px-3 py-3 font-medium text-slate-900 align-top">{row.proyecto}</td>
                  <td class="px-3 py-3 whitespace-nowrap align-top">{row.cliente}</td>
                  <td class="px-3 py-3 align-top">
                    <div class="flex items-center gap-2">
                      <span class={`badge badge-sm whitespace-nowrap ${estadoBadge(row.estado)}`}>
                        {estadoLabel(row.estado)}
                      </span>
                    </div>
                  </td>
                  <td class="px-3 py-3 align-top">
                    <p class="text-sm text-slate-800 leading-5 whitespace-nowrap">
                      {getConversationDateInfo(row).primary}
                    </p>
                    <p class="text-xs text-slate-500 leading-5 min-h-5 whitespace-nowrap">
                      {getConversationDateInfo(row).secondary || "\u00A0"}
                    </p>
                  </td>
                  <td class="px-3 py-3 align-top">
                    <p
                      class="text-sm text-slate-700 break-words overflow-hidden text-ellipsis [display:-webkit-box] [-webkit-line-clamp:2] [-webkit-box-orient:vertical] leading-5"
                    >
                      {row.ultimoMensaje}
                    </p>
                  </td>
                  <td class="px-3 py-3 align-top text-right">
                    {#if getRowActions(row).length > 0}
                      <div class="flex justify-end gap-2 flex-wrap">
                        {#each getRowActions(row) as action}
                          <button
                            type="button"
                            class={actionClass(action.tone)}
                            onclick={() => executeConversationAction(action.id, row)}
                            disabled={Boolean(action.disabled)}
                            title={action.id === "confirm" && !hasActiveProposal(row.ticketId)
                              ? "No hay propuesta activa para confirmar"
                              : ""}
                          >
                            {action.label}
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
  supervisorSending={supervisorSending}
  onSupervisorSend={handleSupervisorSend}
  onClose={closeLeadDetail}
/>
