<script>
  import { tick } from "svelte";

  let {
    open = false,
    lead = null,
    messages = null,
    loadingMessages = false,
    supervisorSending = false,
    onSupervisorSend = null,
    onClose = () => {},
  } = $props();

  const ADVISOR_BY_PROJECT = {
    OBRA_PALERMO_01: {
      name: "Sofia Ruiz",
      phone: "+54 9 11 7000-1001",
    },
    OBRA_NUNEZ_02: {
      name: "Martin Diaz",
      phone: "+54 9 11 7000-1002",
    },
    OBRA_CABALLITO_03: {
      name: "Lucia Romero",
      phone: "+54 9 11 7000-1003",
    },
    OBRA_BELGRANO_04: {
      name: "Nicolas Bianchi",
      phone: "+54 9 11 7000-1004",
    },
  };

  const getAdvisor = (row) =>
    ADVISOR_BY_PROJECT[row?.proyecto] || {
      name: "Asesor demo",
      phone: "+54 9 11 7000-1999",
    };

  const formatClock = (value) => {
    if (!value) return "--:--";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "--:--";
    return new Intl.DateTimeFormat("es-AR", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(parsed);
  };

  const roleBadgeClass = (role) => {
    if (role === "Cliente") return "badge-primary";
    if (role === "Asesor") return "badge-success";
    if (role === "Supervisor") return "badge-warning";
    return "badge-neutral";
  };

  const alignmentClass = (role) => {
    if (role === "Cliente") return "justify-start";
    if (role === "AI") return "justify-start";
    return "justify-end";
  };

  const bubbleClass = (role) => {
    if (role === "Cliente") return "bg-base-200 text-slate-900";
    if (role === "Asesor") return "bg-emerald-100 text-emerald-900";
    if (role === "Supervisor") return "bg-amber-100 text-amber-900";
    return "bg-slate-100 text-slate-800";
  };

  const buildConversation = (row) => {
    const baseMs = new Date(row?.lastActivityAt || row?.createdAt || Date.now()).getTime();
    const entry = (id, role, text, minutesBefore, trace) => ({
      id: `${row?.id || "lead"}-${id}`,
      role,
      text,
      timestamp: new Date(baseMs - minutesBefore * 60 * 1000).toISOString(),
      trace,
    });

    const advisor = getAdvisor(row);
    return [
      entry(
        "m01",
        "Cliente",
        `Hola, vi ${row?.proyecto} y me interesa coordinar visita.`,
        115,
        `Cliente -> ${advisor.name}`,
      ),
      entry(
        "m02",
        "AI",
        "Gracias por escribir. Tomo tus datos y te conecto con el asesor del proyecto.",
        110,
        "AI -> Cliente",
      ),
      entry(
        "m03",
        "Asesor",
        "Perfecto, soy tu asesor asignado. ¿Qué día te queda mejor esta semana?",
        102,
        `${advisor.name} -> Cliente`,
      ),
      entry(
        "m04",
        "Cliente",
        "Podría lunes o martes después de las 17:00.",
        96,
        "Cliente -> Asesor",
      ),
      entry(
        "m05",
        "AI",
        "Registro preferencia horaria: lunes o martes después de las 17:00.",
        90,
        "AI -> Workflow",
      ),
      entry(
        "m06",
        "Asesor",
        "Te propongo lunes 18:00 o martes 17:30. ¿Cuál preferís?",
        74,
        `${advisor.name} -> Cliente`,
      ),
      entry(
        "m07",
        "Cliente",
        "Martes 17:30 me sirve, quedo atento.",
        63,
        "Cliente -> Asesor",
      ),
      entry(
        "m08",
        "Supervisor",
        "Reviso conversación: mantener seguimiento hasta confirmación final.",
        50,
        `Supervisor -> ${advisor.name}`,
      ),
      entry(
        "m09",
        "Asesor",
        "Confirmado. Te envío ubicación y punto de encuentro.",
        39,
        `${advisor.name} -> Cliente`,
      ),
      entry(
        "m10",
        "AI",
        "Evento actualizado: visita en progreso de confirmación.",
        28,
        "AI -> Sistema",
      ),
    ];
  };

  const normalizeIncomingMessage = (item, index) => ({
    id: String(item?.id || `msg-${index + 1}`),
    role: String(item?.role || "AI"),
    text: String(item?.text || ""),
    timestamp: item?.timestamp || null,
    trace: String(item?.trace || ""),
  });

  let initializedLeadId = $state("");
  let draftMessage = $state("");
  let recipientTarget = $state("client");
  let conversation = $state([]);
  let conversationViewport;

  const recipientOptions = (row) => {
    const advisor = getAdvisor(row);
    return [
      {
        key: "client",
        label: "Cliente potencial",
        name: "Cliente",
        phone: row?.cliente || "--",
      },
      {
        key: "advisor",
        label: `Asesor (${advisor.name})`,
        name: advisor.name,
        phone: advisor.phone,
      },
    ];
  };

  $effect(() => {
    if (!open || !lead?.id) return;
    if (initializedLeadId === lead.id) return;

    initializedLeadId = lead.id;
    recipientTarget = "client";
    draftMessage = "";

    if (Array.isArray(messages)) {
      conversation = messages.map((item, index) => normalizeIncomingMessage(item, index));
      return;
    }

    conversation = buildConversation(lead);
  });

  $effect(() => {
    if (!open || !lead?.id || !Array.isArray(messages)) return;
    conversation = messages.map((item, index) => normalizeIncomingMessage(item, index));
  });

  const appendSupervisorMessage = async () => {
    const trimmed = draftMessage.trim();
    if (!trimmed || !lead || supervisorSending) return;

    const target = recipientOptions(lead).find((item) => item.key === recipientTarget);

    if (typeof onSupervisorSend === "function") {
      await onSupervisorSend({
        target: recipientTarget,
        text: trimmed,
        lead,
      });
      draftMessage = "";
      return;
    }

    const nowIso = new Date().toISOString();
    conversation = [
      ...conversation,
      {
        id: `${lead.id}-sup-${Date.now()}`,
        role: "Supervisor",
        text: trimmed,
        timestamp: nowIso,
        trace: `Supervisor -> ${target?.name || "--"} (${target?.phone || "--"})`,
      },
    ];
    draftMessage = "";
    await tick();
    if (conversationViewport) {
      conversationViewport.scrollTop = conversationViewport.scrollHeight;
    }
  };

  const handleClose = () => {
    onClose();
  };
</script>

<dialog class={`modal ${open ? "modal-open" : ""}`} aria-label="Detalle de lead">
  <div class="modal-box h-screen w-screen max-w-none rounded-none p-0 md:h-[92vh] md:w-11/12 md:max-w-5xl md:rounded-2xl flex flex-col overflow-hidden">
    <header class="sticky top-0 z-20 border-b border-base-300 bg-base-100 px-4 py-3 md:px-5">
      <button
        type="button"
        class="btn btn-ghost btn-sm absolute right-2 top-2 md:right-3 md:top-3"
        aria-label="Cerrar detalle"
        onclick={handleClose}
      >
        ✕
      </button>
      <h3 class="text-lg font-semibold text-slate-900">Detalle de lead</h3>
      <p class="mt-1 text-sm text-slate-700 break-words">
        {lead?.proyecto || "--"} • {lead?.cliente || "--"}
      </p>
      <div class="mt-2 flex flex-wrap items-center gap-2 pr-8">
        <span class="badge badge-outline">{lead?.estado || "--"}</span>
        <span class="badge badge-warning">Supervisor (Demo)</span>
        <span class="text-xs text-slate-600">
          Asesor asignado: <span class="font-medium">{getAdvisor(lead).name}</span>
        </span>
      </div>
    </header>

    <div class="flex-1 overflow-y-auto px-4 py-4 md:px-5" bind:this={conversationViewport}>
      <div class="mb-3 flex items-center justify-between">
        <h4 class="text-sm font-semibold uppercase tracking-wide text-slate-600">
          Conversación
        </h4>
        <span class="text-xs text-slate-500">{conversation.length} mensajes</span>
      </div>

      {#if loadingMessages}
        <div class="alert alert-info">
          <span>Cargando historial real...</span>
        </div>
      {:else if conversation.length === 0}
        <div class="alert alert-warning">
          <span>Sin mensajes para este ticket.</span>
        </div>
      {:else}
        <div class="space-y-3 pb-4">
          {#each conversation as item}
            <article class={`flex ${alignmentClass(item.role)}`}>
              <div class={`max-w-[92%] md:max-w-[76%] rounded-2xl px-3 py-2 ${bubbleClass(item.role)}`}>
                <div class="mb-1 flex items-center gap-2">
                  <span class={`badge badge-xs whitespace-nowrap ${roleBadgeClass(item.role)}`}>
                    {item.role}
                  </span>
                  <span class="text-[11px] text-slate-500">{formatClock(item.timestamp)}</span>
                </div>
                <p class="text-sm whitespace-pre-wrap break-words">{item.text}</p>
                <p class="mt-1 text-[11px] text-slate-500">{item.trace}</p>
              </div>
            </article>
          {/each}
        </div>
      {/if}
    </div>

    <footer class="border-t border-base-300 bg-base-100 px-4 py-3 md:px-5">
      <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Composer Supervisor
      </p>
      <div class="mt-2 grid gap-2 md:grid-cols-[1fr_auto] md:items-end">
        <div class="space-y-2">
          <label class="form-control">
            <span class="label-text text-xs">Enviar a</span>
            <select
              class="select select-bordered min-h-11 w-full"
              bind:value={recipientTarget}
              disabled={supervisorSending}
            >
              {#each recipientOptions(lead) as option}
                <option value={option.key}>
                  {option.label} - {option.phone}
                </option>
              {/each}
            </select>
          </label>
          <label class="form-control">
            <span class="label-text text-xs">Mensaje del supervisor</span>
            <textarea
              class="textarea textarea-bordered min-h-24"
              bind:value={draftMessage}
              placeholder="Escribí una intervención con trazabilidad..."
              disabled={supervisorSending}
            ></textarea>
          </label>
        </div>
        <button
          type="button"
          class="btn btn-primary min-h-11"
          onclick={appendSupervisorMessage}
          disabled={supervisorSending}
        >
          {supervisorSending ? "Enviando..." : "Enviar intervención"}
        </button>
      </div>
    </footer>
  </div>

  <form method="dialog" class="modal-backdrop">
    <button type="button" onclick={handleClose}>close</button>
  </form>
</dialog>
