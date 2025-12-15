<script lang="ts">
  import { onMount } from "svelte";
  import { URL_REST } from "./global";

  let health = $state<Record<string, unknown> | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      const res = await fetch(`${URL_REST}/health`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      health = await res.json();
    } catch (err) {
      error = err instanceof Error ? err.message : "Unknown error";
    } finally {
      loading = false;
    }
  });
</script>

<div class="card bg-base-100 shadow-md">
  <div class="card-body">
    <h3 class="card-title">/health</h3>
    {#if loading}
      <span class="loading loading-spinner loading-sm" aria-label="Loading health status"></span>
    {:else if error}
      <div class="text-error text-sm">Error: {error}</div>
    {:else if health}
      <pre class="bg-neutral text-neutral-content p-3 rounded text-sm overflow-x-auto">{JSON.stringify(health, null, 2)}</pre>
    {/if}
  </div>
</div>
