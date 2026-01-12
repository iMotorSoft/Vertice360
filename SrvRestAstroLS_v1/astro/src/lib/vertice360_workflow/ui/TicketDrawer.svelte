<script>
  import { channelLabel, statusLabel, statusTone } from "../types";
  import { formatRelative } from "../time";
  import DocsChecklist from "./DocsChecklist.svelte";
  import SlaPanel from "./SlaPanel.svelte";
  import TicketTimeline from "./TicketTimeline.svelte";

  let {
    ticket = null,
    loading = false,
    error = null,
    nowMs = Date.now(),
    onRetry = () => {},
    onAssign = () => {},
    onRequestDocs = () => {},
    onReceiveDocs = () => {},
    onClose = () => {},
    onEscalate = () => {},
    onSimulateBreach = () => {},
  } = $props();

  let activeTab = $state("timeline");
  let slaType = $state("ASSIGNMENT");
  let actionBusy = $state(false);
  let lastTicketId = $state(null);

  const runAction = async (fn) => {
    if (!fn || actionBusy) return;
    actionBusy = true;
    try {
      await fn();
    } finally {
      actionBusy = false;
    }
  };

  const latestMessages = (messages = []) =>
    [...messages].sort((a, b) => (b.at ?? 0) - (a.at ?? 0));

  $effect(() => {
    if (!ticket?.ticketId) return;
    if (ticket.ticketId !== lastTicketId) {
      lastTicketId = ticket.ticketId;
      activeTab = "timeline";
    }
  });
</script>

<div class="h-full">
  {#if loading}
    <div class="p-6 space-y-4">
      <div class="h-10 w-2/3 bg-base-200 rounded-2xl animate-pulse"></div>
      <div class="h-24 bg-base-200 rounded-2xl animate-pulse"></div>
      <div class="h-64 bg-base-200 rounded-2xl animate-pulse"></div>
    </div>
  {:else if error}
    <div class="p-6">
      <div class="alert alert-error">
        <span>{error}</span>
        <button class="btn btn-sm btn-outline" on:click={onRetry}
          >Reintentar</button
        >
      </div>
    </div>
  {:else if !ticket}
    <div class="flex h-full items-center justify-center p-10 text-center">
      <div class="space-y-3">
        <div class="text-4xl">💬</div>
        <h3 class="text-xl font-semibold text-slate-800">
          Selecciona un ticket
        </h3>
        <p class="text-sm text-slate-500">
          Explora el inbox para ver actividad y SLA.
        </p>
      </div>
    </div>
  {:else}
    {#key ticket.ticketId}
      <div class="p-6 space-y-5 animate-fade-slide">
        <header class="space-y-4">
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div class="space-y-1">
              <div class="flex items-center gap-2">
                <span class="text-xs uppercase tracking-[0.2em] text-slate-400"
                  >{ticket.ticketId}</span
                >
                <span class={`badge badge-sm ${statusTone(ticket.status)}`}
                  >{statusLabel(ticket.status)}</span
                >
                {#if channelLabel(ticket.channel)}
                  <span class="badge badge-outline badge-sm"
                    >{channelLabel(ticket.channel)}</span
                  >
                {/if}
              </div>
              <h3 class="text-2xl font-semibold text-slate-900">
                {ticket.subject || "Ticket sin asunto"}
              </h3>
              <p class="text-sm text-slate-500">
                {ticket.customer?.displayName ||
                  ticket.customer?.from ||
                  "Cliente"} · Actualizado {formatRelative(
                  ticket.updatedAt,
                  nowMs,
                )}
              </p>
              {#if ticket.assignee?.name}
                <p class="text-xs text-slate-400">
                  Asignado a {ticket.assignee.name}
                </p>
              {/if}
            </div>
            <div class="flex flex-wrap gap-2">
              <button
                class="btn btn-sm btn-primary rounded-full"
                on:click={() => runAction(onAssign)}
                disabled={actionBusy}
              >
                Asignar a Administracion
              </button>
              <button
                class="btn btn-sm btn-secondary rounded-full"
                on:click={() => runAction(onRequestDocs)}
                disabled={actionBusy}
              >
                Solicitar docs
              </button>
              <button
                class="btn btn-sm btn-outline rounded-full"
                on:click={() => runAction(onReceiveDocs)}
                disabled={actionBusy}
              >
                Marcar docs recibidas
              </button>
              <button
                class="btn btn-sm btn-accent rounded-full"
                on:click={() => runAction(onClose)}
                disabled={actionBusy}
              >
                Validar y cerrar
              </button>
              <button
                class="btn btn-sm btn-error rounded-full"
                on:click={() => runAction(onEscalate)}
                disabled={actionBusy}
              >
                Escalar
              </button>
              <div class="flex items-center gap-2">
                <select
                  class="select select-sm select-bordered rounded-full"
                  bind:value={slaType}
                >
                  <option value="ASSIGNMENT">SLA Assignment</option>
                  <option value="DOC_VALIDATION">SLA Doc Validation</option>
                </select>
                <button
                  class="btn btn-sm btn-outline rounded-full"
                  on:click={() => runAction(() => onSimulateBreach?.(slaType))}
                  disabled={actionBusy}
                >
                  Simular breach
                </button>
              </div>
            </div>
          </div>

          <SlaPanel sla={ticket.sla} createdAt={ticket.createdAt} {nowMs} />
        </header>

        <div class="tabs tabs-bordered">
          <button
            class={`tab ${activeTab === "timeline" ? "tab-active font-semibold" : ""}`}
            on:click={() => (activeTab = "timeline")}
          >
            Timeline
          </button>
          <button
            class={`tab ${activeTab === "messages" ? "tab-active font-semibold" : ""}`}
            on:click={() => (activeTab = "messages")}
          >
            Mensajes
          </button>
          <button
            class={`tab ${activeTab === "docs" ? "tab-active font-semibold" : ""}`}
            on:click={() => (activeTab = "docs")}
          >
            Docs
          </button>
        </div>

        {#if activeTab === "timeline"}
          <TicketTimeline timeline={ticket.timeline} {nowMs} />
        {:else if activeTab === "messages"}
          <div class="space-y-3">
            {#if !ticket.messages || ticket.messages.length === 0}
              <div
                class="rounded-2xl border border-dashed border-base-300 p-6 text-center text-slate-500"
              >
                <p class="font-semibold">Sin mensajes aun</p>
                <p class="text-sm">Cuando llegue un WhatsApp, se vera aqui.</p>
              </div>
            {:else}
              <div class="space-y-3">
                {#each latestMessages(ticket.messages) as msg (msg.messageId || msg.at)}
                  <div
                    class={`flex ${msg.direction === "outbound" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      class={`max-w-[70%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                        msg.direction === "outbound"
                          ? "bg-primary text-white"
                          : "bg-base-200 text-slate-800"
                      }`}
                    >
                      <p class="whitespace-pre-wrap">
                        {msg.text || "(sin texto)"}
                      </p>
                      <div
                        class="mt-2 text-[10px] opacity-70 flex items-center justify-between gap-2"
                      >
                        <span
                          >{msg.direction === "outbound"
                            ? "Outbound"
                            : "Inbound"}</span
                        >
                        <span>{formatRelative(msg.at, nowMs)}</span>
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {:else}
          <DocsChecklist
            requestedDocs={ticket.requestedDocs}
            docsReceivedAt={ticket.docsReceivedAt}
            {nowMs}
          />
        {/if}
      </div>
    {/key}
  {/if}
</div>
