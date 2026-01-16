<script>
  import { CHANNEL_LABELS, channelLabel, statusLabel, statusTone } from "../types";
  import { formatCountdown, formatRelative } from "../time";

  let {
    tickets = [],
    loading = false,
    error = null,
    selectedId = null,
    search = "",
    onSearch = () => {},
    onSelect = () => {},
    onRetry = () => {},
    nowMs = Date.now(),
  } = $props();

  const getInitials = (ticket) => {
    const name =
      ticket?.customer?.displayName ||
      ticket?.customer?.from ||
      ticket?.ticketId ||
      "?";
    return name.trim().slice(0, 1).toUpperCase();
  };

  const nextSla = (ticket) => {
    const sla = ticket?.sla || {};
    const candidates = [sla.assignmentDueAt, sla.docValidationDueAt].filter(
      Boolean,
    );
    if (!candidates.length) return null;
    return Math.min(...candidates);
  };

  const isInboxTicket = (ticket) => {
    const id = ticket?.ticketId;
    if (typeof id === "string" && id.startsWith("VTX-")) return true;
    const channel = typeof ticket?.channel === "string" ? ticket.channel.toLowerCase() : "";
    if (channel && CHANNEL_LABELS[channel]) return true;
    return Boolean(ticket?.provider);
  };

  const visibleTickets = $derived(
    (() => tickets.filter((ticket) => isInboxTicket(ticket)))(),
  );

  const filtered = $derived(
    (() => {
      const query = search.trim().toLowerCase();
      if (!query) return visibleTickets;
      return visibleTickets.filter((ticket) => {
        const haystack = [
          ticket.ticketId,
          ticket.subject,
          ticket.customer?.displayName,
          ticket.customer?.from,
          ticket.lastMessageText,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(query);
      });
    })(),
  );
</script>

<div class="space-y-4">
  <div class="flex items-center justify-between gap-3">
    <div>
      <h3 class="text-lg font-semibold text-slate-900">Inbox</h3>
      <p class="text-xs text-slate-500">{visibleTickets.length} tickets activos</p>
    </div>
    <label
      class="input input-sm input-bordered flex items-center gap-2 rounded-full"
    >
      <span class="text-xs text-slate-400">Buscar</span>
      <input
        class="grow"
        type="text"
        placeholder="Nombre, ticket, mensaje"
        value={search}
        on:input={(event) => onSearch?.(event.currentTarget.value)}
      />
    </label>
  </div>

  {#if loading}
    <div class="space-y-3">
      {#each Array.from({ length: 5 }) as _, idx}
        <div
          class="h-20 rounded-2xl bg-base-200/70 animate-pulse"
          aria-hidden="true"
        ></div>
      {/each}
    </div>
  {:else if error}
    <div class="alert alert-error">
      <span>{error}</span>
      <button class="btn btn-sm btn-outline" on:click={onRetry}
        >Reintentar</button
      >
    </div>
  {:else if filtered.length === 0}
    <div
      class="rounded-2xl border border-dashed border-base-300 p-6 text-center text-slate-500"
    >
      <div class="text-3xl mb-2">📭</div>
      <p class="font-semibold">Esperando mensajes de WhatsApp</p>
      <p class="text-sm">Las conversaciones apareceran aqui en segundos.</p>
    </div>
  {:else}
    <div class="space-y-3">
      {#each filtered as ticket (ticket.ticketId)}
        <button
          class={`w-full text-left rounded-2xl border transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md ${
            selectedId === ticket.ticketId
              ? "border-primary/50 bg-primary/5 shadow-sm"
              : "border-base-200 bg-base-100"
          } ${ticket.pulse ? "ring-2 ring-primary/40 shadow-lg animate-pulse" : ""}`}
          on:click={() => onSelect?.(ticket.ticketId)}
        >
          <div class="p-4 space-y-3">
            <div class="flex items-start justify-between gap-3">
              <div class="flex items-center gap-3">
                <div class="avatar placeholder">
                  <div class="bg-slate-900 text-white rounded-full w-10">
                    <span>{getInitials(ticket)}</span>
                  </div>
                </div>
                <div>
                  <div class="flex items-center gap-2">
                    <span class="font-semibold text-slate-900"
                      >{ticket.customer?.displayName ||
                        ticket.customer?.from ||
                        "Contacto"}</span
                    >
                    <span class={`badge badge-sm ${statusTone(ticket.status)}`}
                      >{statusLabel(ticket.status)}</span
                    >
                  </div>
                  <p class="text-xs text-slate-500">
                    {ticket.ticketId} · {ticket.subject || "Sin asunto"}
                  </p>
                </div>
              </div>
              <div class="text-right text-xs text-slate-400">
                <span
                  >{ticket.lastMessageAt
                    ? formatRelative(ticket.lastMessageAt, nowMs)
                    : "-"}</span
                >
              </div>
            </div>

            <div class="flex items-center justify-between gap-2">
              <span
                class="inline-flex items-center gap-2 text-xs text-slate-500"
              >
                {#if channelLabel(ticket.channel)}
                  <span class="badge badge-outline badge-sm"
                    >{channelLabel(ticket.channel)}</span
                  >
                {/if}
                <span class="truncate max-w-[180px]"
                  >{ticket.lastMessageText || "Sin mensajes"}</span
                >
              </span>
              <span class="text-xs font-semibold text-slate-700">
                {#if ticket.sla?.assignmentBreachedAt || ticket.sla?.docValidationBreachedAt}
                  <span class="badge badge-error badge-sm">BREACHED</span>
                {:else}
                  {formatCountdown(nextSla(ticket), nowMs)}
                {/if}
              </span>
            </div>
          </div>
        </button>
      {/each}
    </div>
  {/if}
</div>
