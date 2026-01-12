<script>
  import { EVENT_GROUPS } from "../types";
  import { formatClock, formatRelative } from "../time";

  let {
    events = [],
    filters = { text: "", type: "all", onlySelected: false },
    selectedTicketId = null,
    nowMs = Date.now(),
    onFilterChange = () => {},
    onCopy = () => {},
  } = $props();

  let activeEvent = $state(null);
  let modalRef;

  const matchesType = (eventName) => {
    if (filters.type === "all") return true;
    return eventName?.startsWith(`${filters.type}.`);
  };

  const matchesText = (event) => {
    if (!filters.text) return true;
    const query = filters.text.toLowerCase();
    const haystack =
      `${event.name} ${event.correlationId} ${JSON.stringify(event.value)}`.toLowerCase();
    return haystack.includes(query);
  };

  const matchesTicket = (event) => {
    if (!filters.onlySelected) return true;
    if (!selectedTicketId) return false;
    return event.correlationId === selectedTicketId;
  };

  const filteredEvents = $derived(
    events.filter(
      (evt) => matchesType(evt.name) && matchesText(evt) && matchesTicket(evt),
    ),
  );

  const preview = (evt) => {
    if (!evt?.value) return "-";
    const text = JSON.stringify(evt.value);
    return text.length > 80 ? `${text.slice(0, 80)}...` : text;
  };

  const openModal = (evt) => {
    activeEvent = evt;
    modalRef?.showModal?.();
  };

  const copyEvent = async (evt) => {
    const payload = JSON.stringify(evt.raw ?? evt, null, 2);
    try {
      await navigator.clipboard.writeText(payload);
      onCopy?.("Evento copiado");
    } catch (err) {
      onCopy?.("No se pudo copiar");
    }
  };
</script>

<div
  class="collapse collapse-arrow rounded-2xl border border-base-200 bg-white/80 shadow-sm"
>
  <input type="checkbox" />
  <div
    class="collapse-title text-lg font-semibold text-slate-900 flex items-center justify-between"
  >
    <span>Live Event Log</span>
    <span class="text-xs text-slate-400">{filteredEvents.length} eventos</span>
  </div>
  <div class="collapse-content space-y-4">
    <div class="grid gap-3 md:grid-cols-[1fr,200px,200px]">
      <label
        class="input input-sm input-bordered flex items-center gap-2 rounded-full"
      >
        <span class="text-xs text-slate-400">Filtrar</span>
        <input
          class="grow"
          type="text"
          placeholder="ticket.*, mensaje, id"
          value={filters.text}
          on:input={(event) =>
            onFilterChange({ text: event.currentTarget.value })}
        />
      </label>
      <select
        class="select select-sm select-bordered rounded-full"
        value={filters.type}
        on:change={(event) =>
          onFilterChange({ type: event.currentTarget.value })}
      >
        {#each EVENT_GROUPS as group}
          <option value={group.id}>{group.label}</option>
        {/each}
      </select>
      <label class="label cursor-pointer justify-start gap-2">
        <input
          type="checkbox"
          class="checkbox checkbox-sm"
          checked={filters.onlySelected}
          on:change={(event) =>
            onFilterChange({ onlySelected: event.currentTarget.checked })}
        />
        <span class="label-text text-sm text-slate-600"
          >Solo ticket seleccionado</span
        >
      </label>
    </div>

    {#if filteredEvents.length === 0}
      <div
        class="rounded-2xl border border-dashed border-base-300 p-6 text-center text-slate-500"
      >
        <p class="font-semibold">Sin eventos visibles</p>
        <p class="text-sm">Ajusta filtros o espera nuevos eventos SSE.</p>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="table table-sm">
          <thead>
            <tr class="text-slate-400 text-xs">
              <th>Hora</th>
              <th>Evento</th>
              <th>Ticket</th>
              <th>Preview</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each filteredEvents as evt (evt.id)}
              <tr class="text-sm">
                <td>
                  <div class="text-xs text-slate-500">
                    {formatClock(evt.timestamp)}
                  </div>
                  <div class="text-[10px] text-slate-400">
                    {formatRelative(evt.timestamp, nowMs)}
                  </div>
                </td>
                <td class="font-semibold text-slate-900">{evt.name}</td>
                <td class="text-xs text-slate-500"
                  >{evt.correlationId || "-"}</td
                >
                <td class="text-xs text-slate-500 max-w-[240px] truncate"
                  >{preview(evt)}</td
                >
                <td class="text-right">
                  <div class="flex items-center justify-end gap-2">
                    <button
                      class="btn btn-ghost btn-xs"
                      on:click={() => openModal(evt)}>Ver JSON</button
                    >
                    <button
                      class="btn btn-ghost btn-xs"
                      on:click={() => copyEvent(evt)}>Copy JSON</button
                    >
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</div>

<dialog class="modal" bind:this={modalRef}>
  <div class="modal-box max-w-3xl">
    <h3 class="font-semibold text-lg text-slate-900">
      Evento {activeEvent?.name}
    </h3>
    <p class="text-xs text-slate-400">Ticket: {activeEvent?.correlationId}</p>
    <pre class="mt-4 bg-base-200 rounded-2xl p-4 text-xs overflow-auto">
{JSON.stringify(activeEvent?.raw ?? activeEvent, null, 2)}
    </pre>
    <div class="modal-action">
      <button class="btn btn-ghost" on:click={() => modalRef?.close?.()}
        >Cerrar</button
      >
      <button
        class="btn btn-primary"
        on:click={() => activeEvent && copyEvent(activeEvent)}>Copy JSON</button
      >
    </div>
  </div>
  <form method="dialog" class="modal-backdrop">
    <button>close</button>
  </form>
</dialog>
