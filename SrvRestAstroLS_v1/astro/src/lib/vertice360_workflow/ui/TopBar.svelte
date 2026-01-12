<script>
  let {
    connected = false,
    onReset = () => {},
    onRefresh = () => {},
  } = $props();
</script>

<div
  class="rounded-2xl border border-base-200 bg-white/80 backdrop-blur shadow-sm"
>
  <div
    class="flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between"
  >
    <div class="space-y-1">
      <p class="text-xs uppercase tracking-[0.3em] text-slate-400">
        Workflow Ops
      </p>
      <h2 class="text-2xl md:text-3xl font-semibold text-slate-900">
        Vértice360 • Atención Inteligente
      </h2>
      <p class="text-sm text-slate-500">
        Inbox y automatizaciones con trazabilidad SSE global.
      </p>
    </div>
    <div class="flex flex-wrap items-center gap-2">
      <span
        class={`badge gap-2 px-3 py-3 font-semibold ${connected ? "badge-success" : "badge-error"}`}
        aria-live="polite"
      >
        <span
          class={`h-2 w-2 rounded-full ${connected ? "bg-success" : "bg-error"}`}
        ></span>
        {connected ? "LIVE" : "OFFLINE"}
      </span>
      <button class="btn btn-sm btn-outline rounded-full" on:click={onRefresh}>
        Refrescar
      </button>
      <button class="btn btn-sm btn-primary rounded-full" on:click={onReset}>
        Reset demo
      </button>
    </div>
  </div>
</div>
