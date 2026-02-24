<script>
  import { URL_SVG_XMLNS, URL_WA_ME } from "../../global.js";
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

<div class="mx-auto w-full max-w-7xl space-y-4 px-4 sm:px-5 lg:px-6">
  <header class="card-primary">
    <div class="card-body p-5 md:p-6">
      <div class="flex gap-4">
        <div class="w-1.5 bg-emerald-700 rounded-full self-stretch"></div>
        <div class="min-w-0 flex-1">
          <div
            class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"
          >
            <div class="min-w-0 flex items-start gap-3">
              <div
                class="flex h-10 w-10 md:h-12 md:w-12 items-center justify-center
                rounded-2xl bg-emerald-700/10 text-emerald-700 text-sm md:text-base font-bold"
              >
                V
              </div>
              <div class="min-w-0">
                <h1 class="text-2xl leading-tight">Orquestador</h1>
                <p
                  class="mt-1 text-sm text-base-content/60 break-all sm:break-normal"
                >
                  Cliente activo: {normalizeClienteDisplay(cliente) ||
                    "Sin cliente"}
                </p>
              </div>
            </div>
            <div class="flex items-center justify-between gap-2 sm:justify-end">
              <span class="badge badge-neutral badge-outline">Demo</span>
              <a
                href="/demo/vertice360-orquestador/ux"
                class="btn-secondary h-11"
              >
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

  <section class="card-primary">
    <div class="card-body p-4 md:p-6">
      <h2 class="text-base md:text-lg font-semibold text-slate-900">
        Ejemplos de publicidad
      </h2>
      <p class="mt-1 text-sm text-slate-700">
        Elegí un proyecto y abrí WhatsApp con el código listo para consultar.
      </p>
      <p class="text-xs text-slate-500">
        Vas a ver la conversación y su estado reflejados en el Orquestador.
      </p>
      <div class="mt-3 grid gap-4 md:grid-cols-3">
        {#each ads as ad, i}
          <article
            class="card-primary border border-base-300 flex flex-col min-h-96 max-w-80"
          >
            <img
              src={`/depto${i + 1}.jpg`}
              alt={ad.title}
              class="h-28 w-full rounded-t-2xl object-cover shrink-0"
            />
            <div
              class="card-body p-4 gap-2 flex flex-col flex-1 justify-between"
            >
              <div class="flex flex-col gap-2">
                <h3 class="font-semibold text-slate-900">{ad.title}</h3>
                <div class="space-y-1 flex-1">
                  <p class="text-sm text-slate-600 break-words">
                    {ad.line1}
                  </p>
                  <p class="text-sm text-slate-600 break-words">
                    {ad.line2}
                  </p>
                </div>
              </div>
              <div class="flex flex-col gap-2">
                <div class="flex flex-wrap gap-1 flex-1">
                  {#each ad.chips || [] as chip}
                    <span class="badge badge-outline badge-sm">{chip}</span>
                  {/each}
                </div>
                <a
                  href={buildWhatsAppUrl(ad.title)}
                  target="_blank"
                  rel="noreferrer"
                  class="btn-primary h-11 shrink-0"
                >
                  <svg
                    xmlns={URL_SVG_XMLNS}
                    viewBox="0 0 24 24"
                    class="h-4 w-4 fill-current"
                    aria-hidden="true"
                  >
                    <path
                      d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"
                    />
                  </svg>
                  Enviar WhatsApp
                </a>
              </div>
            </div>
          </article>
        {/each}
      </div>
    </div>
  </section>

  <section class="card-primary">
    <div class="card-body p-4 md:p-5">
      <h2 class="text-base md:text-lg font-semibold text-slate-900">
        Actividad en tiempo real
      </h2>
      <div class="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3">
        {#each kpis as kpi}
          <div class="card-primary p-3">
            <p class="text-xs uppercase tracking-wide text-slate-500">
              {kpi.label}
            </p>
            <p class="mt-1 text-2xl font-bold text-slate-900">{kpi.value}</p>
          </div>
        {/each}
      </div>
    </div>
  </section>

  <section class="card-primary">
    <div class="card-body p-4 md:p-5 gap-3">
      <h2 class="text-base md:text-lg font-semibold text-slate-900">
        Conversaciones y estado
      </h2>

      <div class="md:hidden space-y-3">
        {#each conversations as row}
          <article class="card-primary p-3 space-y-2">
            <div class="flex items-start justify-between gap-2">
              <div>
                <p class="text-sm font-semibold text-slate-900">
                  {row.proyecto}
                </p>
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
                    title={actionLabel(action.id)}
                    onclick={() => executeConversationAction(action.id, row)}
                  >
                    {@html actionIcon(action.id)}
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
                <th class="px-3 py-3 whitespace-nowrap">Proyecto</th>
                <th class="px-3 py-3 whitespace-nowrap">Cliente</th>
                <th class="px-3 py-3 whitespace-nowrap">Estado</th>
                <th class="px-3 py-3 whitespace-nowrap">Fecha/Hora</th>
                <th class="px-3 py-3">Último mensaje</th>
                <th class="px-3 py-3 whitespace-nowrap text-right">Acción</th>
              </tr>
            </thead>
            <tbody>
              {#each conversations as row}
                <tr>
                  <td class="px-3 py-3 font-medium text-slate-900 align-top">
                    {row.proyecto}
                  </td>
                  <td class="px-3 py-3 whitespace-nowrap align-top"
                    >{row.cliente}</td
                  >
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
                  <td class="px-3 py-3 align-top">
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
                  <td class="px-3 py-3 align-top">
                    <p
                      class="text-sm text-slate-700 break-words overflow-hidden text-ellipsis
                       [display:-webkit-box] [-webkit-line-clamp:2] [-webkit-box-orient:vertical]
                       leading-5"
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
