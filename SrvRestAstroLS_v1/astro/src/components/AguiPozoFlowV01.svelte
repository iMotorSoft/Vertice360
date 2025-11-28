<script lang="ts">
  import { API_BASE_URL } from "../config/api";
  import { DEFAULT_LOCALE, STRINGS } from "../config/strings";

  const locale = DEFAULT_LOCALE;
  const strings = STRINGS[locale];

  let text = $state("Describe la operación de obra en pozo...");
  let result = $state<Record<string, unknown> | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);

  const runFlow = async () => {
    loading = true;
    error = null;
    result = null;

    try {
      const res = await fetch(`${API_BASE_URL}/api/agui/pozo/flow/v1/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      result = await res.json();
    } catch (err) {
      error = err instanceof Error ? err.message : "Unknown error";
    } finally {
      loading = false;
    }
  };
</script>

<!-- Laboratory UI for agui_pozo_flow_v01 (UI -> Endpoint -> Classifier -> Extractor -> Postprocess -> Validator -> UI) -->
<div class="card bg-base-100 shadow-md">
  <div class="card-body space-y-4">
    <h3 class="card-title">{strings.aguiFlowTitle}</h3>
    <label class="form-control">
      <div class="label">
        <span class="label-text text-sm">Descripción</span>
      </div>
      <textarea
        class="textarea textarea-bordered h-32"
        bind:value={text}
        placeholder="Ej: Quiero reservar una unidad de 80m2 en el proyecto Demo a USD 150k"
      ></textarea>
    </label>
    <div class="card-actions justify-end">
      <button class="btn btn-primary" on:click={runFlow} disabled={loading}>
        {#if loading}
          <span class="loading loading-spinner loading-xs"></span>
        {/if}
        Procesar
      </button>
    </div>
    {#if error}
      <div class="text-error text-sm">Error: {error}</div>
    {/if}
    {#if result}
      <pre class="bg-neutral text-neutral-content p-3 rounded text-sm overflow-x-auto">{JSON.stringify(result, null, 2)}</pre>
    {/if}
  </div>
</div>
