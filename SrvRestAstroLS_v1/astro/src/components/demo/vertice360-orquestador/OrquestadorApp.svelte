<script>
  import LeadDetailModal from "./LeadDetailModal.svelte";
  import VisitProposalModal from "./VisitProposalModal.svelte";
  import {
    orquestadorAds,
    orquestadorConversations,
    orquestadorKpis,
  } from "../../../lib/vertice360_orquestador_mock/data.js";

  let { initialCliente = "", clientPhone = "" } = $props();

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
      primary: activityAt ? `Último: ${formatDateTime(activityAt)}` : "Sin actividad",
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
    if (estado === "Nuevo") return "badge-info";
    if (estado === "En seguimiento") return "badge-warning";
    if (estado === "Pendiente de visita") return "badge-primary";
    if (estado === "Esperando confirmación") return "badge-accent";
    if (estado === "Visita confirmada") return "badge-success";
    return "badge-ghost";
  };

  const isPendingVisit = (estado) => estado === "Pendiente de visita";
  const isWaitingConfirmation = (estado) =>
    estado === "Esperando confirmación" || estado === "Esperando conf.";
  const isVisitConfirmed = (estado) => estado === "Visita confirmada";
  const isGeneralFollowUp = (estado) =>
    estado === "Nuevo" ||
    estado === "En seguimiento" ||
    estado === "Esperando respuesta";

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

    return [...quickActions.slice(0, 2), { id: "view", label: "Ver", tone: "ghost" }];
  };

  const actionClass = (tone) => {
    const base = "btn btn-sm min-h-11 md:btn-xs md:min-h-[28px] whitespace-nowrap";
    if (tone === "primary") return `${base} btn-primary`;
    if (tone === "success") return `${base} btn-success`;
    if (tone === "outline") return `${base} btn-outline`;
    return `${base} btn-ghost`;
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
    `https://wa.me/${demoWhatsAppPhone}/?text=${encodeURIComponent(projectCode)}`;

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
            ultimoMensaje: payload?.mensaje || "Te comparto opciones para coordinar una visita.",
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
      const mode = isWaitingConfirmation(row.estado) ? "ver_propuesta" : "proponer";
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
              <span class="badge badge-primary badge-outline">Demo</span>
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
      <div class="mt-3 grid gap-3 md:grid-cols-3">
        {#each ads as ad}
          <article class="card border border-base-300 bg-base-100">
            <div class="h-28 rounded-t-2xl bg-slate-200"></div>
            <div class="card-body p-4 gap-2">
              <h3 class="font-semibold text-slate-900">{ad.title}</h3>
              <div class="space-y-1">
                <p class="text-sm text-slate-600 break-words">
                  {ad.line1}
                </p>
                <p class="text-sm text-slate-600 break-words">
                  {ad.line2}
                </p>
              </div>
              <div class="flex flex-wrap gap-1">
                {#each ad.chips || [] as chip}
                  <span class="badge badge-outline badge-sm">{chip}</span>
                {/each}
              </div>
              <a
                href={buildWhatsAppUrl(ad.title)}
                target="_blank"
                rel="noreferrer"
                class="btn btn-sm min-h-11 border-0 bg-[#25D366] text-white hover:bg-[#1EBE5D] inline-flex items-center gap-2"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
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
            <p class="text-xs uppercase tracking-wide text-slate-500">
              {kpi.label}
            </p>
            <p class="mt-1 text-2xl font-bold text-slate-900">{kpi.value}</p>
          </div>
        {/each}
      </div>
    </div>
  </section>

  <section class="card border border-base-300 bg-base-100 shadow-sm">
    <div class="card-body p-4 md:p-5 gap-3">
      <h2 class="text-base md:text-lg font-semibold text-slate-900">
        Conversaciones y estado
      </h2>

      <div class="md:hidden space-y-3">
        {#each conversations as row}
          <article
            class="rounded-2xl border border-base-300 bg-base-100 p-3 space-y-2"
          >
            <div class="flex items-start justify-between gap-2">
              <div>
                <p class="text-sm font-semibold text-slate-900">
                  {row.proyecto}
                </p>
                <p class="text-xs text-slate-500">{row.cliente}</p>
              </div>
              <div class="flex items-center gap-2">
                <span class={`badge badge-sm whitespace-nowrap ${estadoBadge(row.estado)}`}>
                  {estadoLabel(row.estado)}
                </span>
                {#if isAiHandled(row)}
                  <span class="badge badge-outline badge-xs whitespace-nowrap">AI</span>
                {/if}
              </div>
            </div>
            <p
              class="text-sm text-slate-700 break-words overflow-hidden text-ellipsis [display:-webkit-box] [-webkit-line-clamp:2] [-webkit-box-orient:vertical] leading-5"
            >
              {row.ultimoMensaje}
            </p>
            <div class="space-y-1">
              <p class="text-xs text-slate-600">
                {getConversationDateInfo(row).primary}
              </p>
              <p class="text-xs text-slate-500 min-h-4">
                {getConversationDateInfo(row).secondary || "\u00A0"}
              </p>
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
                  <td class="px-3 py-3 font-medium text-slate-900 align-top">
                    {row.proyecto}
                  </td>
                  <td class="px-3 py-3 whitespace-nowrap align-top">{row.cliente}</td>
                  <td class="px-3 py-3 align-top">
                    <div class="flex items-center gap-2">
                      <span class={`badge badge-sm whitespace-nowrap ${estadoBadge(row.estado)}`}>
                        {estadoLabel(row.estado)}
                      </span>
                      {#if isAiHandled(row)}
                        <span class="badge badge-outline badge-xs whitespace-nowrap">AI</span>
                      {/if}
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
  onClose={closeVisitModal}
  onSubmit={sendVisitOptions}
/>

<LeadDetailModal
  open={detailModalOpen}
  lead={selectedLead}
  onClose={closeLeadDetail}
/>
