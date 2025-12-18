<script lang="ts">
  import { relativeTime, formatDateTime } from "../../../lib/crm/time";

  type Task = {
    id: string;
    title: string;
    leadId: string;
    dealId?: string | null;
    dueAt: string;
    status: string;
  };

  type Deal = {
    id: string;
    title: string;
  };

  type ComponentProps = {
    tasks?: Task[];
    loading?: boolean;
    error?: string | null;
    pipeline?: Deal[];
    selectedConversation?: { leadId: string } | null;
    onCreate?: (input: { title: string; leadId: string; dealId?: string; dueAt: string }) => void;
    onComplete?: (id: string) => void;
  };

  let {
    tasks = [],
    loading = false,
    error = null,
    pipeline = [],
    selectedConversation = null,
    onCreate,
    onComplete,
  } = $props<ComponentProps>();

  let showModal = $state(false);
  let titleInput = $state("");
  let dueAtInput = $state("");
  let dealIdInput = $state("");
  let leadIdInput = $state(selectedConversation?.leadId ?? "");

  $effect(() => {
    leadIdInput = selectedConversation?.leadId ?? "";
  });

  const openModal = () => {
    showModal = true;
    dueAtInput = new Date(Date.now() + 3600 * 1000).toISOString().slice(0, 16);
  };

  const closeModal = () => {
    showModal = false;
    titleInput = "";
    dealIdInput = "";
  };

  const createTask = () => {
    if (!titleInput.trim() || !leadIdInput.trim() || !dueAtInput) return;
    onCreate?.({ title: titleInput.trim(), leadId: leadIdInput.trim(), dealId: dealIdInput || undefined, dueAt: dueAtInput });
    closeModal();
  };

  const pendingTasks = () => tasks.filter((t) => t.status !== "completed");
  const completedTasks = () => tasks.filter((t) => t.status === "completed");
</script>

<div class="p-4 space-y-4">
  <div class="flex items-center justify-between">
    <div>
      <p class="text-xs uppercase tracking-wide text-slate-500 font-semibold">Tareas</p>
      <h3 class="text-lg font-semibold text-slate-900">Seguimiento operativo</h3>
    </div>
    <button class="btn btn-primary btn-sm rounded-full" on:click={openModal}>
      <span class="icon-[heroicons-plus-20-solid]"></span>
      Nueva
    </button>
  </div>

  {#if error}
    <div class="alert alert-error text-sm">{error}</div>
  {:else}
    <div class="space-y-4">
      <div class="space-y-2">
        <h4 class="text-sm font-semibold text-slate-700">Pendientes</h4>
        {#if loading}
          {#each Array(2) as _, idx}
            <div class="animate-pulse rounded-xl border border-base-200 p-3" aria-label={`task-skel-${idx}`}>
              <div class="h-4 w-2/3 bg-base-200 rounded"></div>
              <div class="mt-2 h-3 w-1/3 bg-base-200 rounded"></div>
            </div>
          {/each}
        {:else if pendingTasks().length === 0}
          <p class="text-xs text-slate-500">Nada pendiente. Respirá :)</p>
        {:else}
          {#each pendingTasks() as task (task.id)}
            <div class="rounded-xl border border-base-200 p-3 flex items-start justify-between gap-3">
              <div class="space-y-1">
                <p class="font-semibold text-slate-900">{task.title}</p>
                <p class="text-xs text-slate-500">Lead {task.leadId}</p>
                <p class="text-xs text-slate-500">Vence {formatDateTime(task.dueAt)} ({relativeTime(task.dueAt)})</p>
              </div>
              <div class="flex items-center gap-2">
                {#if task.dealId}
                  <span class="badge badge-ghost badge-sm">Deal {task.dealId}</span>
                {/if}
                <button class="btn btn-circle btn-ghost btn-xs" on:click={() => onComplete?.(task.id)} aria-label="Completar">
                  <span class="icon-[heroicons-check-20-solid] text-success"></span>
                </button>
              </div>
            </div>
          {/each}
        {/if}
      </div>

      <div class="space-y-2">
        <h4 class="text-sm font-semibold text-slate-700">Completadas</h4>
        {#if loading}
          <p class="text-xs text-slate-500">Cargando...</p>
        {:else if completedTasks().length === 0}
          <p class="text-xs text-slate-500">Aún no hay tareas completadas.</p>
        {:else}
          <div class="space-y-2">
            {#each completedTasks() as task (task.id)}
              <div class="rounded-xl border border-base-200 bg-base-200/40 p-3 flex items-center justify-between">
                <div>
                  <p class="font-semibold text-slate-800 line-through">{task.title}</p>
                  <p class="text-xs text-slate-500">Lead {task.leadId}</p>
                </div>
                <span class="badge badge-success badge-outline">Completada</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {/if}

  {#if showModal}
    <div class="modal modal-open">
      <div class="modal-box space-y-3">
        <h3 class="font-semibold text-lg">Nueva tarea</h3>
        <div class="form-control">
          <label class="label">
            <span class="label-text">Título</span>
          </label>
          <input class="input input-bordered" bind:value={titleInput} placeholder="Ej: Enviar brochure" />
        </div>
        <div class="grid gap-3 md:grid-cols-2">
          <div class="form-control">
            <label class="label">
              <span class="label-text">Lead ID</span>
            </label>
            <input class="input input-bordered" bind:value={leadIdInput} placeholder="lead-1001" />
          </div>
          <div class="form-control">
            <label class="label">
              <span class="label-text">Deal</span>
            </label>
            <select class="select select-bordered" bind:value={dealIdInput}>
              <option value="">Sin deal</option>
              {#each pipeline as deal (deal.id)}
                <option value={deal.id}>{deal.title}</option>
              {/each}
            </select>
          </div>
        </div>
        <div class="form-control">
          <label class="label">
            <span class="label-text">Vencimiento</span>
          </label>
          <input type="datetime-local" class="input input-bordered" bind:value={dueAtInput} />
        </div>
        <div class="modal-action">
          <button class="btn btn-ghost" on:click={closeModal}>Cancelar</button>
          <button class="btn btn-primary" on:click={createTask}>Crear</button>
        </div>
      </div>
    </div>
  {/if}
</div>
