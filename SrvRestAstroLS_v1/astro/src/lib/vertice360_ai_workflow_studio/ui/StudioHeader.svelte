<script>
  let { connectionStatus = "disconnected", onRefresh = () => {}, onClear = () => {} } = $props();

  const statusLabel = () => (connectionStatus === "connected" ? "SSE live" : "SSE offline");
  const statusTone = () => (connectionStatus === "connected" ? "badge-success" : "badge-ghost");
</script>

<div class="flex flex-wrap items-center justify-between gap-4 min-w-0">
  <div class="space-y-2">
    <p class="text-xs uppercase tracking-[0.3em] text-slate-500 font-semibold">Workflow control</p>
    <h2 class="text-2xl md:text-3xl font-semibold text-slate-900">Vertice360 AI Workflow Studio</h2>
    <p class="text-sm text-neutral-600 max-w-xl">
      Ejecuta flujos deterministas, valida intenciones y observa eventos en tiempo real.
    </p>
  </div>

  <div class="flex flex-wrap items-center gap-3 min-w-0">
    <div class={`badge badge-lg ${statusTone()}`}>{statusLabel()}</div>
    <button class="btn btn-outline btn-sm" on:click={onRefresh}>Refresh runs</button>
    <button class="btn btn-ghost btn-sm" on:click={onClear}>Clear events</button>
  </div>
</div>
