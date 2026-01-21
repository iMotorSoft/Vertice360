<script>
  import { formatTime, statusLabel, statusTone } from "../types";

  let {
    runs = [],
    selectedRunId = null,
    activeRunId = null,
    onSelect = () => {},
    onRefresh = () => {},
    autoFocusNewest = true,
    setAutoFocusNewest = () => {},
  } = $props();

  const isSelected = (runId) => runId && runId === selectedRunId;
</script>

<div
  class="card overflow-hidden border border-base-200 bg-base-100/90 shadow-sm"
>
  <div class="card-body gap-4 p-5">
    <div class="flex flex-wrap items-center justify-between gap-3 min-w-0">
      <div>
        <p
          class="text-xs uppercase tracking-[0.3em] text-slate-500 font-semibold"
        >
          Runs
        </p>
        <h3 class="text-lg font-semibold text-slate-900">History</h3>
      </div>
      <div class="flex items-center gap-2">
        <button
          class={`btn btn-xs ${autoFocusNewest ? "btn-primary" : "btn-ghost"}`}
          onclick={() => setAutoFocusNewest(!autoFocusNewest)}
          title="Auto-follow new runs"
        >
          {autoFocusNewest ? "Following" : "Follow"}
        </button>
        <button class="btn btn-ghost btn-sm" onclick={onRefresh}>Load</button>
      </div>
    </div>

    <div class="space-y-2 max-h-[40vh] overflow-y-auto pr-1">
      {#if runs.length === 0}
        <div
          class="rounded-2xl border border-dashed border-base-300 p-4 text-sm text-neutral-500"
        >
          No runs yet.
        </div>
      {:else}
        {#each runs as run}
          <button
            class={`w-full rounded-2xl border px-4 py-3 text-left transition ${
              isSelected(run.runId)
                ? "border-primary/40 bg-primary/10"
                : "border-base-200 bg-white"
            }`}
            onclick={() => onSelect(run.runId)}
          >
            <div class="flex items-center justify-between gap-2 min-w-0">
              <div class="text-sm font-semibold text-slate-900 break-words">
                {run.runId}
              </div>
              <span class={`badge badge-sm ${statusTone(run.status)}`}
                >{statusLabel(run.status)}</span
              >
            </div>
            <div
              class="mt-1 flex items-center justify-between text-xs text-neutral-500 min-w-0"
            >
              <span>{formatTime(run.startedAt)}</span>
              {#if run.runId === activeRunId}
                <span class="text-primary">active</span>
              {:else}
                <span>{run.stepCount || (run.steps || []).length} steps</span>
              {/if}
            </div>
          </button>
        {/each}
      {/if}
    </div>
  </div>
</div>
