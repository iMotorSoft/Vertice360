<script>
  import { shortId } from "../types";

  let {
    events = [],
    activeRunId = null,
    activeTicketId = null,
    onFilter = (type) => {},
    activeFilter = "all",
  } = $props();

  const recent = $derived.by(() => (events || []).slice(0, 60));

  const matchTicket = (event) => {
    if (!activeTicketId) return true;
    return (
      event?.correlationId === activeTicketId ||
      event?.data?.ticketId === activeTicketId
    );
  };

  const matchRun = (event) => {
    if (!activeRunId) return true;
    return (
      event?.correlationId === activeRunId || event?.data?.runId === activeRunId
    );
  };

  const inboundOn = $derived.by(() =>
    recent.some(
      (event) =>
        (event.name === "messaging.inbound" ||
          event.name === "messaging.inbound.raw") &&
        matchTicket(event),
    ),
  );
  const aiOn = $derived.by(() =>
    recent.some(
      (event) => event.name?.startsWith("ai_workflow.") && matchRun(event),
    ),
  );
  const outboundOn = $derived.by(() =>
    recent.some(
      (event) => event.name === "messaging.outbound" && matchTicket(event),
    ),
  );
  const statusOn = $derived.by(() =>
    recent.some((event) => {
      if (event.name !== "messaging.status") return false;
      const status = String(
        event.data?.status || event.summary || "",
      ).toLowerCase();
      return status.includes("delivered") || status.includes("read");
    }),
  );

  const segmentClass = (active, filterName) => {
    const isSelected = activeFilter === filterName;
    const base = "cursor-pointer transition hover:shadow-md";
    if (isSelected) {
      return `${base} border-emerald-500 ring-1 ring-emerald-500 bg-emerald-50`;
    }
    return active
      ? `${base} border-emerald-200 bg-emerald-50`
      : `${base} border-base-200 bg-base-100/80 hover:bg-base-200`;
  };
  const dotClass = (active) => (active ? "bg-emerald-500" : "bg-slate-300");
</script>

<div
  class="card overflow-hidden border border-base-200 bg-base-100/90 shadow-sm"
>
  <div class="card-body gap-4 p-5">
    <div class="flex flex-wrap items-center justify-between gap-3 min-w-0">
      <div class="min-w-0">
        <p
          class="text-xs uppercase tracking-[0.3em] text-slate-500 font-semibold"
        >
          Journey bar
        </p>
        <h3 class="text-lg font-semibold text-slate-900">
          Inbound -> AI -> Outbound -> Status
        </h3>
      </div>
      <div class="flex flex-col items-end text-xs text-neutral-500 min-w-0">
        <span class="truncate">Run: {shortId(activeRunId)}</span>
        <span class="truncate">Ticket: {shortId(activeTicketId)}</span>
      </div>
    </div>

    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 min-w-0">
      <button
        type="button"
        class={`text-left rounded-2xl border p-3 min-w-0 ${segmentClass(inboundOn, "messaging.inbound")}`}
        onclick={() => onFilter("messaging.inbound")}
      >
        <div class="flex items-center gap-2 min-w-0">
          <span class={`h-2 w-2 rounded-full ${dotClass(inboundOn)}`}></span>
          <span class="text-xs uppercase tracking-[0.2em] text-slate-500"
            >Inbound</span
          >
        </div>
        <p class="mt-2 text-sm font-semibold text-slate-900">
          {inboundOn ? "Received" : "Waiting"}
        </p>
      </button>

      <button
        type="button"
        class={`text-left rounded-2xl border p-3 min-w-0 ${segmentClass(aiOn, "ai")}`}
        onclick={() => onFilter("ai")}
      >
        <div class="flex items-center gap-2 min-w-0">
          <span class={`h-2 w-2 rounded-full ${dotClass(aiOn)}`}></span>
          <span class="text-xs uppercase tracking-[0.2em] text-slate-500"
            >AI</span
          >
        </div>
        <p class="mt-2 text-sm font-semibold text-slate-900">
          {aiOn ? "Processing" : "Idle"}
        </p>
      </button>

      <button
        type="button"
        class={`text-left rounded-2xl border p-3 min-w-0 ${segmentClass(outboundOn, "messaging.outbound")}`}
        onclick={() => onFilter("messaging.outbound")}
      >
        <div class="flex items-center gap-2 min-w-0">
          <span class={`h-2 w-2 rounded-full ${dotClass(outboundOn)}`}></span>
          <span class="text-xs uppercase tracking-[0.2em] text-slate-500"
            >Outbound</span
          >
        </div>
        <p class="mt-2 text-sm font-semibold text-slate-900">
          {outboundOn ? "Sent" : "Pending"}
        </p>
      </button>

      <button
        type="button"
        class={`text-left rounded-2xl border p-3 min-w-0 ${segmentClass(statusOn, "messaging.status")}`}
        onclick={() => onFilter("messaging.status")}
      >
        <div class="flex items-center gap-2 min-w-0">
          <span class={`h-2 w-2 rounded-full ${dotClass(statusOn)}`}></span>
          <span class="text-xs uppercase tracking-[0.2em] text-slate-500"
            >Status</span
          >
        </div>
        <p class="mt-2 text-sm font-semibold text-slate-900">
          {statusOn ? "Delivered" : "Waiting"}
        </p>
      </button>
    </div>
  </div>
</div>
