<script>
  import { formatRelative } from "../time";

  let {
    requestedDocs = [],
    docsReceivedAt = null,
    nowMs = Date.now(),
  } = $props();
</script>

<div class="space-y-4">
  <div class="flex items-center justify-between">
    <div>
      <h4 class="text-lg font-semibold text-slate-900">
        Checklist de documentos
      </h4>
      <p class="text-xs text-slate-500">{requestedDocs.length} requeridos</p>
    </div>
    {#if docsReceivedAt}
      <span class="badge badge-success"
        >Recibidos {formatRelative(docsReceivedAt, nowMs)}</span
      >
    {/if}
  </div>

  {#if !requestedDocs || requestedDocs.length === 0}
    <div
      class="rounded-2xl border border-dashed border-base-300 p-6 text-center text-slate-500"
    >
      <p class="font-semibold">Sin documentos solicitados</p>
      <p class="text-sm">Usa "Solicitar docs" para iniciar la validacion.</p>
    </div>
  {:else}
    <div class="space-y-2">
      {#each requestedDocs as doc}
        <div
          class="flex items-center justify-between rounded-2xl border border-base-200 bg-white/70 p-3 shadow-sm"
        >
          <div class="flex items-center gap-3">
            <input
              type="checkbox"
              class="checkbox checkbox-sm"
              checked={!!docsReceivedAt}
              disabled
            />
            <span class="text-sm text-slate-700">{doc}</span>
          </div>
          {#if docsReceivedAt}
            <span class="text-xs text-slate-400">OK</span>
          {:else}
            <span class="text-xs text-slate-400">Pendiente</span>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
