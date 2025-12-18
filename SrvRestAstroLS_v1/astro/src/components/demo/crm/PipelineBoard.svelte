<script lang="ts">
  type Deal = {
    id: string;
    leadId: string;
    title: string;
    stageId: string;
    amount: number;
    currency: string;
  };

  type Stage = { id: string; title: string };

  type ComponentProps = {
    deals?: Deal[];
    stages?: Stage[];
    loading?: boolean;
    error?: string | null;
    onMove?: (dealId: string, stageId: string) => void;
  };

  let { deals = [], stages = [], loading = false, error = null, onMove } = $props<ComponentProps>();

  let draggingId = $state<string | null>(null);

  const stageColumns = () => {
    const cols = stages.map((stage) => ({ ...stage, items: deals.filter((d) => d.stageId === stage.id) }));
    const orphan = deals.filter((d) => !stages.some((s) => s.id === d.stageId));
    if (orphan.length && cols.length) {
      cols[0].items = [...cols[0].items, ...orphan];
    }
    return cols;
  };

  const handleDrop = (stageId: string) => {
    if (draggingId) {
      onMove?.(draggingId, stageId);
      draggingId = null;
    }
  };

  const formatAmount = (amount: number, currency: string) =>
    new Intl.NumberFormat("es-AR", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount ?? 0);
</script>

<div class="p-4">
  <div class="flex items-center justify-between mb-3">
    <div>
      <p class="text-xs uppercase tracking-wide text-slate-500 font-semibold">Pipeline</p>
      <h3 class="text-lg font-semibold text-slate-900">Etapas comerciales</h3>
    </div>
    {#if loading}
      <span class="loading loading-spinner loading-xs text-primary"></span>
    {/if}
  </div>

  {#if error}
    <div class="alert alert-error text-sm">{error}</div>
  {:else}
    <div class="grid gap-3 md:grid-cols-3 xl:grid-cols-3">
      {#each stageColumns() as stage (stage.id)}
        <div
          class="rounded-2xl border border-base-200 bg-base-100/80 backdrop-blur shadow-sm flex flex-col"
          on:dragover|preventDefault
          on:drop={() => handleDrop(stage.id)}
        >
          <div class="flex items-center justify-between p-3">
            <div class="flex items-center gap-2">
              <span class="font-semibold text-slate-800">{stage.title}</span>
              <span class="badge badge-ghost badge-sm">{stage.items.length}</span>
            </div>
          </div>
          <div class="space-y-2 px-3 pb-3 min-h-[120px]">
            {#if loading}
              {#each Array(2) as _, idx}
                <div class="animate-pulse rounded-xl border border-base-200 p-3" aria-label={`pipeline-skel-${idx}`}>
                  <div class="h-4 w-2/3 bg-base-200 rounded"></div>
                  <div class="mt-2 h-3 w-1/3 bg-base-200 rounded"></div>
                </div>
              {/each}
            {:else if stage.items.length === 0}
              <div class="text-xs text-slate-500 py-6 text-center">Sin deals</div>
            {:else}
              {#each stage.items as deal (deal.id)}
                <div
                  class={`rounded-xl border p-3 shadow-sm bg-base-100 cursor-grab active:cursor-grabbing transition ${
                    draggingId === deal.id ? "ring ring-primary/50" : ""
                  }`}
                  draggable="true"
                  on:dragstart={() => (draggingId = deal.id)}
                  on:dragend={() => (draggingId = null)}
                >
                  <div class="flex items-start justify-between gap-2">
                    <div>
                      <p class="font-semibold text-slate-900">{deal.title}</p>
                      <p class="text-xs text-slate-500">Lead {deal.leadId}</p>
                    </div>
                    <div class="text-right text-sm font-semibold text-slate-800">
                      {formatAmount(deal.amount, deal.currency)}
                    </div>
                  </div>
                </div>
              {/each}
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
