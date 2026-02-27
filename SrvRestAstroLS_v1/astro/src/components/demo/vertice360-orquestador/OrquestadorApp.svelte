<script>
  import { URL_SVG_XMLNS, URL_WA_ME } from "../../global.js";
  import LeadDetailModal from "./LeadDetailModal.svelte";
  import VisitProposalModal from "./VisitProposalModal.svelte";
  import {
    orquestadorAds,
    orquestadorConversations,
    orquestadorKpis,
  } from "../../../lib/vertice360_orquestador_mock/data.js";

  // -- Props --
  let { initialCliente = "", clientPhone = "" } = $props();

  // -- Constants & Initial Data --
  const demoCliente = "5491100000000";
  const demoWhatsAppPhone = "4526325250";
  const ads = orquestadorAds;
  const kpis = orquestadorKpis;
  const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  // -- Reactive State --
  let cliente = $state((clientPhone || initialCliente || "").trim());
  let notice = $state("");
  let modalOpen = $state(false);
  let visitModalMode = $state("proponer");
  let selectedConversation = $state(null);
  let detailModalOpen = $state(false);
  let selectedLead = $state(null);
  let isClienteMode = $state(false);
  let conversations = $state(
    orquestadorConversations.map((row) => ({ ...row })),
  );

  // -- UI Formatting Helpers (Pure) --
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
        row.estado === "Esperando confirmación" && row.nextVisitProposalAt
          ? `Propuesta: ${formatDateTime(row.nextVisitProposalAt)}`
          : "",
    };
  };

  const isAiHandled = (row) => Boolean(row.aiHandled || row.aiResponded);

  const estadoLabel = (estado) => {
    if (estado === "Esperando confirmación") return "Esperando conf.";
    return estado;
  };

  const estadoBadge = (estado) => {
    if (estado === "Nuevo") return "bg-sky-100 text-sky-700 border-sky-200";
    if (estado === "En seguimiento")
      return "bg-amber-100 text-amber-700 border-amber-200";
    if (estado === "Pendiente de visita")
      return "bg-violet-100 text-violet-700 border-violet-200";
    if (estado === "Esperando confirmación")
      return "bg-pink-100 text-pink-700 border-pink-200";
    if (estado === "Visita confirmada")
      return "bg-emerald-100 text-emerald-700 border-emerald-200";
    return "bg-slate-100 text-slate-500 border-slate-200";
  };

  const isPendingVisit = (estado) => estado === "Pendiente de visita";
  const isWaitingConfirmation = (estado) =>
    estado === "Esperando confirmación" || estado === "Esperando conf.";
  const isVisitConfirmed = (estado) => estado === "Visita confirmada";
  const isGeneralFollowUp = (estado) =>
    estado === "Nuevo" ||
    estado === "En seguimiento" ||
    estado === "Esperando respuesta";

  // -- Action UI Config Helpers --
  const getRowActions = (row) => {
    const estado = row.estado;
    const ai = isAiHandled(row);
    const quickActions = [];

    if (ai && !isPendingVisit(estado) && !isWaitingConfirmation(estado)) {
      return [{ id: "view", label: "Ver", tone: "ghost" }];
    }

    if (isPendingVisit(estado)) {
      quickActions.push({ id: "visit", label: "Visita", tone: "primary" });
    } else if (isWaitingConfirmation(estado)) {
      quickActions.push({ id: "visit", label: "Visita", tone: "primary" });
      if (!ai) {
        quickActions.push({
          id: "confirm",
          label: "Confirmar",
          tone: "success",
        });
      }
    } else if (isVisitConfirmed(estado)) {
      quickActions.push({
        id: "reschedule",
        label: "Reagendar",
        tone: "outline",
      });
    } else if (isGeneralFollowUp(estado)) {
      // Solo "Ver" para estados de seguimiento general.
    }

    return [
      ...quickActions.slice(0, 2),
      { id: "view", label: "Ver", tone: "ghost" },
    ];
  };

  const actionClass = (tone) => {
    const base =
      "btn btn-sm min-h-11 md:btn-xs md:min-h-[28px] hover:bg-gray-200 rounded-full p-2";
    if (tone === "primary") return `${base} `;
    if (tone === "success") return `${base} `;
    if (tone === "outline") return `${base} `;
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

  const getKpiStyle = (label) => {
    const l = label.toLowerCase();
    if (l.includes("consultas"))
      return {
        bg: "bg-violet-50/50",
        border: "border-violet-100",
        text: "text-violet-600",
        icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
      };
    if (l.includes("leads"))
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
    if (l.includes("propuestas"))
      return {
        bg: "bg-pink-50/50",
        border: "border-pink-100",
        text: "text-pink-600",
        icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
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

  const useDemoCliente = () => {
    cliente = demoCliente;
    isClienteMode = true;
    selectedConversation = null;
    selectedLead = null;
    modalOpen = false;
    detailModalOpen = false;
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("cliente", demoCliente);
      window.history.replaceState({}, "", url.toString());
    }
    notice = "Cliente demo cargado.";
  };

  const readClienteFromUrl = () => {
    if (typeof window === "undefined") return "";
    return (
      new URLSearchParams(window.location.search).get("cliente") ?? ""
    ).trim();
  };

  const syncClienteFromUrl = () => {
    const fromUrl = readClienteFromUrl();
    isClienteMode = Boolean(fromUrl);
    if (fromUrl) {
      cliente = fromUrl;
      selectedConversation = null;
      selectedLead = null;
      modalOpen = false;
      detailModalOpen = false;
    } else {
      cliente = "";
      selectedConversation = null;
      selectedLead = null;
      modalOpen = false;
      detailModalOpen = false;
      notice = "";
    }
  };

  const resetUiState = () => {
    selectedConversation = null;
    selectedLead = null;
    modalOpen = false;
    detailModalOpen = false;
    notice = "";
  };

  $effect(() => {
    syncClienteFromUrl();
    window.addEventListener("popstate", syncClienteFromUrl);
    window.addEventListener("orquestador:reset-ui", resetUiState);
    return () => {
      window.removeEventListener("popstate", syncClienteFromUrl);
      window.removeEventListener("orquestador:reset-ui", resetUiState);
    };
  });

  const buildWhatsAppUrl = (projectCode) =>
    `${URL_WA_ME}/${demoWhatsAppPhone}/?text=${encodeURIComponent(projectCode)}`;

  const openVisitModal = (row, mode = "proponer") => {
    selectedConversation = row;
    visitModalMode = mode;
    modalOpen = true;
  };

  const closeVisitModal = () => {
    modalOpen = false;
  };

  const openLeadDetail = (row) => {
    selectedLead = row;
    detailModalOpen = true;
  };

  const closeLeadDetail = () => {
    detailModalOpen = false;
  };

  // -- Simulation / Mock Methods --
  const sendVisitOptions = (payload) => {
    const nowIso = new Date().toISOString();
    const nextDayIso = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
    const conversationId = selectedConversation?.id;

    if (conversationId) {
      conversations = conversations.map((row) =>
        row.id === conversationId
          ? {
              ...row,
              estado: "Esperando confirmación",
              ultimoMensaje:
                payload?.mensaje ||
                "Te comparto opciones para coordinar una visita.",
              lastActivityAt: nowIso,
              nextVisitProposalAt: nextDayIso,
              visitAt: null,
            }
          : row,
      );
    }

    if (visitModalMode === "reagendar") {
      notice = `Reagenda enviada (UI) para ${payload?.cliente || "cliente demo"}.`;
      return;
    }
    if (visitModalMode === "ver_propuesta") {
      notice = `Propuesta reenviada (UI) para ${payload?.cliente || "cliente demo"}.`;
      return;
    }
    notice = `Opciones enviadas (UI) para ${payload?.cliente || "cliente demo"}.`;
  };

  const simulateConfirmation = (conversationId) => {
    const nowIso = new Date().toISOString();
    conversations = conversations.map((row) =>
      row.id === conversationId
        ? {
            ...row,
            estado: "Visita confirmada",
            ultimoMensaje: "Perfecto, confirmo la opción 1.",
            lastActivityAt: nowIso,
            visitAt: row.nextVisitProposalAt || nowIso,
          }
        : row,
    );
    notice = "Confirmación simulada solo en UI.";
  };

  const executeConversationAction = (actionId, row) => {
    if (actionId === "confirm") {
      simulateConfirmation(row.id);
      return;
    }

    if (actionId === "visit") {
      const mode = isWaitingConfirmation(row.estado)
        ? "ver_propuesta"
        : "proponer";
      openVisitModal(row, mode);
      return;
    }

    if (actionId === "reschedule") {
      openVisitModal(row, "reagendar");
      return;
    }

    if (actionId === "view") {
      openLeadDetail(row);
      return;
    }
  };
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
          class="hidden flex h-10 w-10 md:h-12 md:w-12 items-center justify-center
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
          class="inline-flex sm:inline-flex items-center gap-1.5 bg-teal-50 border border-teal-200
          text-teal-700 font-bold uppercase tracking-wider rounded-full
          px-1.5 py-1 md:px-3 md:py-1.5 text-[8px] md:text-xs shadow-sm"
        >
          <div class="w-1.5 h-1.5 rounded-full bg-teal-500 animate-pulse"></div>
          Modo Demo
        </span>
        <a
          href="/demo/vertice360-orquestador/ux"
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

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-6">
      {#each ads as ad, i}
        <article
          class="group relative bg-white flex flex-col w-full border border-slate-200/50 rounded-2xl
          shadow-sm hover:shadow-xl hover:shadow-emerald-900/5 hover:border-emerald-200 transition-all
          duration-500 hover:-translate-y-1 overflow-hidden"
        >
          <!-- Contenedor Imagen -->
          <div
            class="relative h-40 w-full overflow-hidden shrink-0 bg-slate-100"
          >
            <div
              class="absolute inset-0 bg-gradient-to-t from-slate-900/60 via-transparent to-transparent 
              z-10"
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

          <!-- Cuerpo de la tarjeta -->
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
              <!-- Chips modernos -->
              <div class="flex flex-wrap gap-1">
                {#each ad.chips || [] as chip}
                  <span
                    class="inline-flex items-center px-2 py-1 rounded-lg bg-slate-50 text-slate-600 text-[11px] font-semibold border border-slate-200/80"
                  >
                    {chip}
                  </span>
                {/each}
              </div>

              <!-- Botón -->
              <a
                href={buildWhatsAppUrl(ad.title)}
                target="_blank"
                rel="noreferrer"
                class="btn-primary md:h-11 h-10 shrink-0 flex items-center justify-center gap-2"
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
  </section>

  <section class="card-primary">
    <div class="card-body p-4 md:p-5">
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-lg md:text-2xl font-bold text-slate-700 flex-1">
          Resumen de actividad
        </h1>
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
      <h1 class="text-lg md:text-2xl font-bold text-slate-700">
        Conversaciones y estado
      </h1>

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
                      class={actionClass(action.tone)}
                      title={actionLabel(action.id)}
                      onclick={() => executeConversationAction(action.id, row)}
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
                            class={actionClass(action.tone)}
                            title={actionLabel(action.id)}
                            onclick={() =>
                              executeConversationAction(action.id, row)}
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
  onClose={closeVisitModal}
  onSubmit={sendVisitOptions}
/>

<LeadDetailModal
  open={detailModalOpen}
  lead={selectedLead}
  onClose={closeLeadDetail}
/>
