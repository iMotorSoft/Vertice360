<script>
  import { formatCountdown, formatRelative, progressFromWindow } from "../time";

  let { sla = {}, createdAt = null, nowMs = Date.now() } = $props();

  const buildSlaCard = (type) => {
    if (type === "ASSIGNMENT") {
      return {
        title: "Assignment SLA",
        dueAt: sla?.assignmentDueAt,
        breachedAt: sla?.assignmentBreachedAt,
        startedAt: sla?.assignmentStartedAt || createdAt,
      };
    }
    return {
      title: "Doc Validation SLA",
      dueAt: sla?.docValidationDueAt,
      breachedAt: sla?.docValidationBreachedAt,
      startedAt: sla?.docValidationStartedAt || createdAt,
    };
  };
</script>

<div class="grid gap-4 md:grid-cols-2">
  {#each ["ASSIGNMENT", "DOC_VALIDATION"] as type}
    {#key type}
      {@const card = buildSlaCard(type)}
      <div class="rounded-2xl border border-base-200 bg-white/80 p-4 shadow-sm">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs uppercase tracking-[0.2em] text-slate-400">
              {card.title}
            </p>
            <p class="text-sm text-slate-600">
              {card.dueAt
                ? `Vence ${formatRelative(card.dueAt, nowMs)}`
                : "Sin SLA"}
            </p>
          </div>
          {#if card.breachedAt}
            <span class="badge badge-error">BREACHED</span>
          {/if}
        </div>
        <div class="mt-3">
          <progress
            class={`progress ${card.breachedAt ? "progress-error" : "progress-primary"}`}
            value={progressFromWindow(card.startedAt, card.dueAt, nowMs)}
            max="100"
          ></progress>
          <div
            class="mt-2 text-xs text-slate-500 flex items-center justify-between"
          >
            <span>{formatCountdown(card.dueAt, nowMs, card.breachedAt)}</span>
            <span
              >{card.dueAt
                ? new Date(card.dueAt).toLocaleTimeString("es-AR", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "-"}</span
            >
          </div>
        </div>
      </div>
    {/key}
  {/each}
</div>
