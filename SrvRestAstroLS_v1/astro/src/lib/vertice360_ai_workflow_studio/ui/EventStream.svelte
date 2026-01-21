<script>
  import { formatTime, shortId } from "../types";

  let {
    events = [],
    sseConnected = false,
    eventCount = 0,
    lastEventAt = null,
    activeRunId = null,
    activeTicketId = null,
    setActiveRunId = null,
    setActiveTicketId = null,
    filterType = $bindable("all"),
  } = $props();

  let onlySteps = $state(false);
  let lockActive = $state(false);
  let searchInput = $state("");
  let searchTerm = $state("");
  let debounceTimer = null;

  const hasActive = $derived(Boolean(activeRunId || activeTicketId));

  $effect(() => {
    if (!hasActive && lockActive) {
      lockActive = false;
    }
  });

  $effect(() => {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    const value = searchInput;
    debounceTimer = setTimeout(() => {
      searchTerm = value.trim();
    }, 220);
    return () => clearTimeout(debounceTimer);
  });

  const getEventRunId = (event) =>
    event?.data?.runId || event?.data?.run_id || event?.data?.id || null;

  const getEventTicketId = (event) =>
    event?.data?.ticketId || event?.data?.ticket_id || null;

  const matchesLock = (event) => {
    if (!lockActive || !hasActive) return true;
    const matchRun =
      activeRunId &&
      (event?.correlationId === activeRunId ||
        getEventRunId(event) === activeRunId);
    const matchTicket =
      activeTicketId &&
      (event?.correlationId === activeTicketId ||
        getEventTicketId(event) === activeTicketId);
    return Boolean(matchRun || matchTicket);
  };

  const stringifyEvent = (event) => {
    try {
      return JSON.stringify(event);
    } catch (err) {
      return "";
    }
  };

  const handleEventClick = (event) => {
    const runId = getEventRunId(event);
    const ticketId = getEventTicketId(event);
    if (runId && typeof setActiveRunId === "function") {
      setActiveRunId(runId);
    }
    if (ticketId && typeof setActiveTicketId === "function") {
      setActiveTicketId(ticketId);
    }
  };

  const filtered = $derived.by(() => {
    const term = searchTerm.trim().toLowerCase();
    return (events || []).filter((event) => {
      const name = event?.name || "";
      if (onlySteps && name !== "ai_workflow.run.step") return false;

      // Filter logic
      if (filterType === "ai" && !name.startsWith("ai_workflow.")) return false;
      if (filterType === "messaging" && !name.startsWith("messaging."))
        return false;

      // Granular Journey Bar filters
      if (filterType === "messaging.inbound") {
        return name === "messaging.inbound" || name === "messaging.inbound.raw";
      }
      if (filterType === "messaging.outbound" && name !== "messaging.outbound")
        return false;
      if (filterType === "messaging.status" && name !== "messaging.status")
        return false;
      if (!matchesLock(event)) return false;
      if (!term) return true;
      return stringifyEvent(event).toLowerCase().includes(term);
    });
  });

  const prettyJson = (value) => {
    if (!value) return "{}";
    try {
      const text = JSON.stringify(value, null, 2);
      if (text.length > 1000) {
        return `${text.slice(0, 1000)}...`;
      }
      return text;
    } catch (err) {
      return "{}";
    }
  };
</script>

<div
  class="card overflow-hidden border border-base-200 bg-base-100/90 shadow-sm"
>
  <div class="card-body gap-4 p-5">
    <div class="flex flex-wrap items-center justify-between gap-3 min-w-0">
      <div>
        <p
          class="text-xs uppercase tracking-[0.3em] text-slate-500 font-semibold"
        >
          Live events
        </p>
        <h3 class="text-lg font-semibold text-slate-900">SSE timeline</h3>
      </div>
      <div
        class="flex flex-wrap items-center gap-3 text-xs text-neutral-500 min-w-0"
      >
        <div class="flex items-center gap-2 min-w-0">
          <span
            class={`h-2 w-2 rounded-full ${sseConnected ? "bg-emerald-500" : "bg-slate-300"}`}
          ></span>
          <span>{sseConnected ? "Connected" : "Disconnected"}</span>
        </div>
        <span>Last: {formatTime(lastEventAt)}</span>
        <span>{eventCount} events</span>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-3 min-w-0">
      <div class="flex flex-wrap items-center gap-2 min-w-0">
        <div class="join">
          <button
            class={`btn btn-xs ${filterType === "all" ? "btn-primary" : "btn-ghost"}`}
            on:click={() => (filterType = "all")}
          >
            All
          </button>
          <button
            class={`btn btn-xs ${filterType === "ai" ? "btn-primary" : "btn-ghost"}`}
            on:click={() => (filterType = "ai")}
          >
            AI
          </button>
          <button
            class={`btn btn-xs ${filterType === "messaging" ? "btn-primary" : "btn-ghost"}`}
            on:click={() => (filterType = "messaging")}
          >
            Messaging
          </button>
        </div>
        <label class="flex items-center gap-2 text-xs text-neutral-600 min-w-0">
          <input
            type="checkbox"
            class="checkbox checkbox-xs"
            bind:checked={onlySteps}
          />
          Only steps
        </label>
        {#if hasActive}
          <label
            class="flex items-center gap-2 text-xs text-neutral-600 min-w-0"
          >
            <input
              type="checkbox"
              class="checkbox checkbox-xs"
              bind:checked={lockActive}
            />
            Lock to Active
          </label>
        {/if}
      </div>
      <input
        class="input input-bordered input-sm w-full sm:max-w-[220px]"
        placeholder="Search event payload"
        bind:value={searchInput}
      />
    </div>

    <div class="space-y-3 max-h-[55vh] overflow-y-auto pr-1">
      {#if filtered.length === 0}
        <div
          class="rounded-2xl border border-dashed border-base-300 p-5 text-sm text-neutral-500"
        >
          No events yet. Run the workflow to see live updates.
        </div>
      {:else}
        {#each filtered as event}
          <button
            class="w-full text-left rounded-2xl border border-base-200 bg-white/90 p-4 hover:border-slate-300 transition"
            type="button"
            on:click={() => handleEventClick(event)}
          >
            <div
              class="flex flex-wrap items-center justify-between gap-2 min-w-0"
            >
              <div class="text-xs text-neutral-500">
                {formatTime(event.timestamp)}
              </div>
              <div class="text-xs text-neutral-400">
                {shortId(event.correlationId)}
              </div>
            </div>
            <p class="mt-1 text-sm font-semibold text-slate-900 break-words">
              {event.name}
            </p>
            <p class="text-xs text-neutral-500 break-words">{event.summary}</p>
            <pre
              class="mt-2 text-xs font-mono text-slate-700 whitespace-pre-wrap break-words overflow-x-auto">{prettyJson(
                event.data,
              )}</pre>
          </button>
        {/each}
      {/if}
    </div>
  </div>
</div>
