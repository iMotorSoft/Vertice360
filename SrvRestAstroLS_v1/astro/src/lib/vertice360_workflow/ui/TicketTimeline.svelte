<script>
  import { formatClock, formatDate, formatRelative } from "../time";

  let { timeline = [], nowMs = Date.now() } = $props();

  const toDayKey = (ts) => {
    const date = new Date(ts);
    return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()}`;
  };

  const friendlyLabel = (entry) => {
    if (!entry) return "Evento";
    if (entry.name === "ticket.created") return "Ticket creado";
    if (entry.name === "ticket.assigned")
      return `Asignado a ${entry.value?.assignee?.name || "equipo"}`;
    if (entry.name === "ticket.escalated")
      return `Escalado a ${entry.value?.toTeam || "Supervisor"}`;
    if (entry.name === "ticket.closed") return "Ticket cerrado";
    if (entry.name === "ticket.sla.started")
      return `SLA iniciado (${entry.value?.slaType || ""})`;
    if (entry.name === "ticket.sla.breached")
      return `SLA breached (${entry.value?.slaType || ""})`;
    if (entry.name === "ticket.updated") {
      const patch = entry.value?.patch || {};
      if (patch.status) return `Estado → ${patch.status}`;
      if (patch.requestedDocs)
        return `Docs solicitados (${patch.requestedDocs.length})`;
      if (patch.docsReceivedAt) return "Docs recibidos";
      if (patch.sla) return "SLA actualizado";
      return "Ticket actualizado";
    }
    return entry.name || "Evento";
  };

  const groups = $derived(
    (() => {
      const sorted = [...(timeline || [])].sort(
        (a, b) => (b.timestamp ?? 0) - (a.timestamp ?? 0),
      );
      const map = {};
      sorted.forEach((entry) => {
        const key = toDayKey(entry.timestamp ?? Date.now());
        if (!map[key]) map[key] = [];
        map[key].push(entry);
      });
      return Object.entries(map).map(([key, entries]) => ({ key, entries }));
    })(),
  );
</script>

<div class="space-y-4">
  {#if !timeline || timeline.length === 0}
    <div
      class="rounded-2xl border border-dashed border-base-300 p-6 text-center text-slate-500"
    >
      <p class="font-semibold">Sin actividad aun</p>
      <p class="text-sm">Los eventos del ticket se veran aqui.</p>
    </div>
  {:else}
    {#each groups as group (group.key)}
      <div class="space-y-3">
        <div
          class="flex items-center gap-2 text-xs text-slate-400 uppercase tracking-[0.3em]"
        >
          <span>{formatDate(group.entries[0]?.timestamp)}</span>
          <div class="flex-1 h-px bg-base-300"></div>
        </div>
        <div class="space-y-3">
          {#each group.entries as entry, index (entry.id || `${entry.name}-${entry.timestamp}`)}
            <div
              class="rounded-2xl border border-base-200 bg-white/80 p-4 shadow-sm animate-rise"
              style={`animation-delay:${index * 40}ms`}
            >
              <div class="flex items-start justify-between gap-3">
                <div class="space-y-1">
                  <p class="font-semibold text-slate-900">
                    {friendlyLabel(entry)}
                  </p>
                  <p class="text-xs text-slate-500">{entry.name}</p>
                </div>
                <div class="text-xs text-slate-400 text-right">
                  <div>{formatClock(entry.timestamp)}</div>
                  <div>{formatRelative(entry.timestamp, nowMs)}</div>
                </div>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/each}
  {/if}
</div>
