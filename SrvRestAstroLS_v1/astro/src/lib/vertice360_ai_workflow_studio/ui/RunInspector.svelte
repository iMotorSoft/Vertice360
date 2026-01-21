<script>
  import { sendReply } from "../api";
  import { statusLabel, statusTone } from "../types";

  let { run = null, events = [], activeTicketId = null } = $props();

  let editing = $state(false);
  let draft = $state("");
  let sending = $state(false);
  let sendError = $state("");
  let copied = $state(false);

  const output = $derived(run?.output || {});
  const pragmatics = $derived(output?.pragmatics || {});
  const missingSlots = $derived(pragmatics?.missingSlots || {});
  const missingSlotsCount = $derived(
    Object.values(missingSlots || {}).reduce((total, slots) => {
      if (Array.isArray(slots)) return total + slots.length;
      return total;
    }, 0),
  );
  const secondaryIntents = $derived(formatList(output?.secondaryIntents));
  const entities = $derived(output?.entities || {});
  const responseText = $derived(
    output?.responseText || output?.response_text || "",
  );

  const lastMessage = $derived.by(() => {
    if (!activeTicketId) return null;
    return (events || []).find((event) => {
      if (!event?.name) return false;
      if (event.name !== "messaging.inbound" && event.name !== "messaging.outbound") return false;
      if (event.correlationId === activeTicketId) return true;
      if (event?.data?.ticketId === activeTicketId) return true;
      return false;
    }) || null;
  });

  const replyTo = $derived.by(() => {
    if (!lastMessage) return "";
    if (lastMessage.name === "messaging.outbound") {
      return lastMessage?.data?.to || "";
    }
    return lastMessage?.data?.from || lastMessage?.data?.wa_id || "";
  });

  const currentText = $derived(editing ? draft : responseText);

  $effect(() => {
    if (!editing) {
      draft = responseText || "";
    }
  });

  const canSend = $derived(
    Boolean(activeTicketId && replyTo && currentText && currentText.trim()),
  );

  const handleCopy = async () => {
    if (!currentText.trim()) return;
    try {
      await navigator.clipboard.writeText(currentText);
      copied = true;
      setTimeout(() => (copied = false), 1200);
    } catch (err) {
      copied = false;
    }
  };

  const toggleEdit = () => {
    editing = !editing;
    if (editing) {
      draft = responseText || "";
    }
  };

  const handleSend = async () => {
    if (!canSend || sending) return;
    sending = true;
    sendError = "";
    const result = await sendReply({
      ticketId: activeTicketId,
      to: replyTo,
      text: currentText.trim(),
    });
    sending = false;
    if (!result.ok) {
      sendError = result.error || "Failed to send reply";
      return;
    }
    editing = false;
  };

  function formatList(value) {
    if (!value) return [];
    return Array.isArray(value) ? value : [value];
  }
</script>

<div
  class="card overflow-hidden border border-base-200 bg-base-100/90 shadow-sm min-h-[420px]"
>
  <div class="card-body gap-4 p-5">
    <div class="flex flex-wrap items-center justify-between gap-3 min-w-0">
      <div>
        <p
          class="text-xs uppercase tracking-[0.3em] text-slate-500 font-semibold"
        >
          Run inspector
        </p>
        <h3 class="text-lg font-semibold text-slate-900">Output + context</h3>
      </div>
      {#if run}
        <div class={`badge badge-lg ${statusTone(run.status)}`}>
          {statusLabel(run.status)}
        </div>
      {/if}
    </div>

    {#if !run}
      <div
        class="rounded-2xl border border-dashed border-base-300 p-6 text-sm text-neutral-500"
      >
        Select a run to inspect its output and metadata.
      </div>
    {:else}
      <div class="grid gap-4 min-w-0 overflow-y-auto max-h-[600px] pr-2">
        <div class="flex flex-wrap items-center gap-2 min-w-0">
          <button class="btn btn-outline btn-xs" onclick={handleCopy} disabled={!currentText.trim()}>
            {copied ? "Copied" : "Copiar respuesta"}
          </button>
          <button class="btn btn-ghost btn-xs" onclick={toggleEdit}>
            {editing ? "Cerrar edicion" : "Editar & reenviar"}
          </button>
          {#if activeTicketId && replyTo}
            <button class="btn btn-primary btn-xs" onclick={handleSend} disabled={!canSend || sending}>
              {sending ? "Enviando..." : "Enviar por WhatsApp"}
            </button>
          {/if}
          {#if activeTicketId && replyTo}
            <span class="text-xs text-neutral-500 truncate">
              to: {replyTo}
            </span>
          {/if}
        </div>
        {#if sendError}
          <p class="text-xs text-error">{sendError}</p>
        {/if}
        {#if editing}
          <textarea
            class="textarea textarea-bordered min-h-[120px] w-full text-sm leading-relaxed"
            value={draft}
            oninput={(event) => (draft = event.currentTarget.value)}
          ></textarea>
        {/if}
        <div class="grid gap-3 md:grid-cols-2 min-w-0">
          <div class="rounded-2xl border border-base-200 p-4 min-w-0">
            <p class="text-xs uppercase tracking-[0.2em] text-slate-500">
              Primary intent
            </p>
            <p class="text-base font-semibold text-slate-900 truncate">
              {output.primaryIntent || output.intent || "--"}
            </p>
            <p class="text-xs text-neutral-500 mt-2 truncate">
              Secondary: {secondaryIntents.join(", ") || "--"}
            </p>
          </div>
          <div class="rounded-2xl border border-base-200 p-4 min-w-0">
            <p class="text-xs uppercase tracking-[0.2em] text-slate-500">
              Pragmatics
            </p>
            <p class="text-sm text-slate-900">
              Speech act: {pragmatics.speechAct || "--"}
            </p>
            <p class="text-sm text-slate-900">
              Urgency: {pragmatics.urgency || "--"}
            </p>
            <p class="text-xs text-neutral-500 mt-2">
              Missing slots: {missingSlotsCount}
            </p>
          </div>
        </div>

        <div class="rounded-2xl border border-base-200 p-4 min-w-0">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-500">
            Missing slots
          </p>
          <div class="mt-2 grid gap-2 md:grid-cols-2 min-w-0">
            {#each Object.entries(missingSlots || {}) as [slot, values]}
              <div class="flex flex-wrap items-center gap-2 text-sm min-w-0">
                <span class="badge badge-ghost badge-sm">{slot}</span>
                <span class="text-neutral-600 truncate"
                  >{formatList(values).join(", ") || "--"}</span
                >
              </div>
            {/each}
            {#if Object.keys(missingSlots || {}).length === 0}
              <p class="text-sm text-neutral-500">No missing slots detected.</p>
            {/if}
          </div>
        </div>

        <div class="rounded-2xl border border-base-200 p-4 min-w-0">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-500">
            Entities
          </p>
          <div class="mt-2 grid gap-2 md:grid-cols-2 min-w-0 text-sm">
            <div class="flex flex-wrap gap-2 min-w-0 items-center">
              <span class="badge badge-outline badge-sm">emails</span>
              <span class="truncate"
                >{formatList(entities.emails).join(", ") || "--"}</span
              >
            </div>
            <div class="flex flex-wrap gap-2 min-w-0 items-center">
              <span class="badge badge-outline badge-sm">phones</span>
              <span class="truncate"
                >{formatList(entities.phones).join(", ") || "--"}</span
              >
            </div>
            <div class="flex flex-wrap gap-2 min-w-0 items-center">
              <span class="badge badge-outline badge-sm">dni_cuit</span>
              <span class="truncate"
                >{formatList(entities.dni_cuit).join(", ") || "--"}</span
              >
            </div>
            <div class="flex flex-wrap gap-2 min-w-0 items-center">
              <span class="badge badge-outline badge-sm">amounts</span>
              <span class="truncate"
                >{formatList(entities.amounts).join(", ") || "--"}</span
              >
            </div>
            <div class="flex flex-wrap gap-2 min-w-0 items-center">
              <span class="badge badge-outline badge-sm">addresses</span>
              <span class="truncate"
                >{formatList(entities.addresses).join(", ") || "--"}</span
              >
            </div>
          </div>
        </div>

        <div class="rounded-2xl border border-base-200 p-4 min-w-0">
          <p class="text-xs uppercase tracking-[0.2em] text-slate-500">
            Response
          </p>
          <p
            class="mt-2 text-sm text-slate-900 whitespace-pre-wrap break-words"
          >
            {responseText || "--"}
          </p>
        </div>
      </div>
    {/if}
  </div>
</div>
