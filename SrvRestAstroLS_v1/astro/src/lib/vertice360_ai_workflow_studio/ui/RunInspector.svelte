<script>
  import { sendReply } from "../api";
  import { statusLabel, statusTone } from "../types";

  let { run = null, events = [], activeTicketId = null } = $props();

  let editing = $state(false);
  let draft = $state("");
  let sending = $state(false);
  let sendError = $state("");
  let copied = $state(false);
  let nbqCopied = $state(false);

  const output = $derived(run?.output || {});
  const pragmatics = $derived(output?.pragmatics || {});
  const missingSlots = $derived(pragmatics?.missingSlots || {});
  const missingSlotsCountComputed = $derived(
    Object.values(missingSlots || {}).reduce((total, slots) => {
      if (Array.isArray(slots)) return total + slots.length;
      return total;
    }, 0),
  );
  const missingSlotsCount = $derived(
    pragmatics?.missingSlotsCount ?? output?.missingSlotsCount ?? missingSlotsCountComputed,
  );
  const secondaryIntents = $derived(formatList(output?.secondaryIntents));
  const entities = $derived(output?.entities || {});
  const responseText = $derived(
    output?.responseText || output?.response_text || "",
  );
  const decision = $derived(output?.decision || "");
  const visitSource = $derived(output?.visit || output?.commercial?.visit || null);
  const visitPreference = $derived.by(() => {
    if (!visitSource) return null;
    if (typeof visitSource === "string") {
      return { day: "", timeWindow: "", rawText: visitSource.trim() };
    }
    const day = firstNonEmptyString(
      visitSource?.day,
      visitSource?.dayOfWeek,
      visitSource?.day_of_week,
      visitSource?.date,
      visitSource?.date_range,
      visitSource?.dateRange,
      visitSource?.fecha,
      visitSource?.dia,
    );
    const timeWindow = firstNonEmptyString(
      visitSource?.timeWindow,
      visitSource?.time_window,
      visitSource?.timeRange,
      visitSource?.time_range,
      visitSource?.window,
      visitSource?.franja,
      visitSource?.horario,
      visitSource?.hora,
    );
    const rawText = firstNonEmptyString(
      visitSource?.rawText,
      visitSource?.raw_text,
      visitSource?.raw,
      visitSource?.text,
      visitSource?.value,
      visitSource?.utterance,
    );
    return { day, timeWindow, rawText };
  });
  const showVisitPreference = $derived(Boolean(visitSource));
  const nextActionQuestion = $derived.by(() => {
    const direct = output?.nextActionQuestion ?? output?.next_action_question;
    if (typeof direct === "string" && direct.trim()) return direct.trim();
    const nextAction = output?.next_action ?? output?.nextAction;
    if (typeof nextAction === "string" && nextAction.trim()) return nextAction.trim();
    if (nextAction && typeof nextAction === "object") {
      const question = nextAction?.question;
      if (typeof question === "string" && question.trim()) return question.trim();
    }
    return "";
  });
  const visitActionQuestion = $derived.by(() => {
    if (decision !== "confirm_visit_request") return "";
    const direct = firstNonEmptyString(
      nextActionQuestion,
      output?.next_question,
      output?.nextQuestion,
    );
    if (direct) return direct;
    if (isQuestionText(responseText)) return responseText.trim();
    return "";
  });

  const nextBestQuestion = $derived.by(() => {
    const direct = output?.recommendedQuestion;
    if (direct) return direct;
    const fromPragmatics = pragmatics?.recommendedQuestion;
    if (fromPragmatics) return fromPragmatics;
    if (decision === "ask_next_best_question") {
      const candidate = output?.responseText;
      if (isQuestionText(candidate)) return candidate.trim();
    }
    return "";
  });
  const showNextBestQuestion = $derived(
    Boolean(nextBestQuestion) || decision === "ask_next_best_question",
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

  const handleCopyNextBestQuestion = async () => {
    if (!nextBestQuestion.trim()) return;
    try {
      await navigator.clipboard.writeText(nextBestQuestion.trim());
      nbqCopied = true;
      setTimeout(() => (nbqCopied = false), 1200);
    } catch (err) {
      nbqCopied = false;
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

  function isQuestionText(value) {
    if (!value || typeof value !== "string") return false;
    const trimmed = value.trim();
    if (!trimmed || trimmed.length > 140) return false;
    return trimmed.endsWith("?") || trimmed.startsWith("¿");
  }

  function firstNonEmptyString(...values) {
    for (const value of values) {
      if (typeof value !== "string") continue;
      const trimmed = value.trim();
      if (trimmed) return trimmed;
    }
    return "";
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

        {#if showVisitPreference}
          <div class="rounded-2xl border border-base-200 p-4 min-w-0">
            <p class="text-xs uppercase tracking-[0.2em] text-slate-500">
              Visit preference
            </p>
            <div class="mt-2 grid gap-2 text-sm min-w-0">
              <div class="flex flex-wrap items-center gap-2 min-w-0">
                <span class="badge badge-outline badge-sm">Day</span>
                <span class="min-w-0 break-words text-slate-700">
                  {visitPreference?.day || "--"}
                </span>
              </div>
              <div class="flex flex-wrap items-center gap-2 min-w-0">
                <span class="badge badge-outline badge-sm">Time window</span>
                <span class="min-w-0 break-words text-slate-700">
                  {visitPreference?.timeWindow || "--"}
                </span>
              </div>
              <div class="flex flex-wrap items-start gap-2 min-w-0">
                <span class="badge badge-ghost badge-sm">Raw</span>
                <span
                  class="min-w-0 break-words whitespace-pre-wrap text-slate-600"
                >
                  {visitPreference?.rawText || "--"}
                </span>
              </div>
            </div>
          </div>
        {/if}

        {#if decision === "confirm_visit_request"}
          <div
            class="rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4 min-w-0"
          >
            <div
              class="flex flex-wrap items-center justify-between gap-2 min-w-0"
            >
              <p
                class="text-xs uppercase tracking-[0.2em] text-emerald-700"
              >
                Next action
              </p>
              <span
                class="badge badge-sm border-emerald-200 bg-emerald-100 text-emerald-700"
              >
                Visit captured
              </span>
            </div>
            <p
              class="mt-3 text-base md:text-lg font-semibold text-emerald-900 break-words whitespace-pre-wrap min-w-0"
            >
              {visitActionQuestion || "--"}
            </p>
          </div>
        {/if}

        {#if showNextBestQuestion}
          <div class="rounded-2xl border border-base-200 p-4 min-w-0">
            <div class="flex flex-wrap items-center justify-between gap-2 min-w-0">
              <p class="text-xs uppercase tracking-[0.2em] text-slate-500">
                Next best question
              </p>
              <div class="flex flex-wrap items-center gap-2 min-w-0">
                {#if decision === "ask_next_best_question"}
                  <span class="badge badge-warning badge-sm">Needs info</span>
                {/if}
                <span class="badge badge-outline badge-sm text-xs">
                  Missing slots: {missingSlotsCount ?? 0}
                </span>
              </div>
            </div>
            <div class="mt-3 flex items-start justify-between gap-3 min-w-0">
              <div
                class="max-w-full overflow-hidden rounded-2xl bg-base-200 px-4 py-3 text-sm text-slate-900 whitespace-pre-wrap break-words"
              >
                {nextBestQuestion || "No question generated yet."}
              </div>
              <button
                class="btn btn-ghost btn-xs"
                onclick={handleCopyNextBestQuestion}
                disabled={!nextBestQuestion.trim()}
              >
                {nbqCopied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
        {/if}

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
