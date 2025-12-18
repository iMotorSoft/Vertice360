<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { crm } from "../../../lib/crm/state.svelte";
  import { connectCrmSSE } from "../../../lib/crm/sse";
  import Inbox from "./Inbox.svelte";
  import ConversationView from "./ConversationView.svelte";
  import PipelineBoard from "./PipelineBoard.svelte";
  import TasksPanel from "./TasksPanel.svelte";
  import LeadTimeline from "./LeadTimeline.svelte";
  import Toast from "./ui/Toast.svelte";
  import EmptyState from "./ui/EmptyState.svelte";
  let activeTab = $state<"pipeline" | "tasks" | "timeline">("pipeline");
  let composerPlaceholder = $state("Escribe un mensaje rápido para tu lead...");

  onMount(() => {
    crm.init();
  });

  $effect(() => {
    if (typeof window === "undefined") return;
    connectCrmSSE();
  });

  onDestroy(() => {
    crm.teardown();
  });

  const quickSimulateInbound = (channel: string) => {
    if (!crm.selectedConversationId) {
      crm.addToast("Selecciona una conversación para simular inbound", "warning");
      return;
    }
    crm.simulateInbound(channel, "Hola! Me interesa saber más sobre Vertice360.");
  };

  const refreshAll = () => crm.refreshAll();
</script>

<section class="space-y-4">
  <div class="rounded-3xl border bg-gradient-to-r from-sky-50 via-white to-emerald-50 shadow-sm">
    <div class="flex flex-col gap-3 p-6 md:flex-row md:items-center md:justify-between">
      <div class="space-y-1">
        <p class="text-xs uppercase tracking-[0.2em] text-sky-600 font-semibold">CRM Demo</p>
        <h2 class="text-2xl font-semibold text-slate-900">Inbox + Pipeline + Tareas en vivo</h2>
        <p class="text-sm text-slate-600">Backend mock + SSE global /api/agui/stream</p>
      </div>
      <div class="flex items-center gap-2">
        <span
          class={`badge ${crm.sse.connected ? "badge-success" : "badge-error"} gap-2 font-semibold shadow-sm`}
          aria-live="polite"
        >
          <span class={`h-2 w-2 rounded-full ${crm.sse.connected ? "bg-success" : "bg-error"}`}></span>
          {crm.sse.connected ? "Live" : "Offline"}
        </span>
        <div class="dropdown dropdown-end">
          <label tabindex="0" class="btn btn-ghost btn-sm rounded-full">Simular inbound</label>
          <ul tabindex="0" class="dropdown-content menu p-2 shadow bg-base-100 rounded-box w-44">
            {#each ["whatsapp", "facebook", "instagram", "email", "webchat"] as channel}
              <li>
                <button type="button" on:click={() => quickSimulateInbound(channel)} class="capitalize">
                  {channel}
                </button>
              </li>
            {/each}
          </ul>
        </div>
        <button class="btn btn-outline btn-sm rounded-full" on:click={refreshAll}>
          <span class="icon-[heroicons-arrow-path-20-solid]"></span>
          Refrescar
        </button>
      </div>
    </div>
  </div>

  <div class="grid gap-4 xl:grid-cols-[340px,1fr,440px]">
    <div class="card bg-base-100 shadow-sm">
      <div class="card-body p-4">
        <Inbox
          conversations={crm.conversations}
          loading={crm.conversationsLoading}
          error={crm.conversationsError}
          selectedId={crm.selectedConversationId}
          search={crm.search}
          channelFilter={crm.channelFilter}
          onSelect={crm.selectConversation}
          onSearch={crm.setSearch}
          onFilter={crm.setChannelFilter}
        />
      </div>
    </div>

    <div class="card bg-base-100 shadow-sm min-h-[70vh]">
      <div class="card-body p-0">
        {#if crm.selectedConversation}
          <ConversationView
            conversation={crm.selectedConversation}
            loading={crm.conversationLoading}
            onSend={crm.sendMessage}
            placeholder={composerPlaceholder}
          />
        {:else}
          <div class="flex h-full items-center justify-center p-10">
            <EmptyState title="Selecciona una conversación" description="Explora el inbox para empezar a chatear." />
          </div>
        {/if}
      </div>
    </div>

    <div class="card bg-base-100 shadow-sm">
      <div class="card-body p-0">
        <div class="tabs tabs-bordered px-4 pt-4">
          <button class={`tab ${activeTab === "pipeline" ? "tab-active font-semibold" : ""}`} on:click={() => (activeTab = "pipeline")}>
            Pipeline
          </button>
          <button class={`tab ${activeTab === "tasks" ? "tab-active font-semibold" : ""}`} on:click={() => (activeTab = "tasks")}>
            Tareas
          </button>
          <button class={`tab ${activeTab === "timeline" ? "tab-active font-semibold" : ""}`} on:click={() => (activeTab = "timeline")}>
            Timeline
          </button>
        </div>

        {#if activeTab === "pipeline"}
          <PipelineBoard
            deals={crm.pipeline}
            stages={crm.stageConfig}
            loading={crm.pipelineLoading}
            error={crm.pipelineError}
            onMove={crm.moveDealToStage}
          />
        {:else if activeTab === "tasks"}
          <TasksPanel
            tasks={crm.tasks}
            loading={crm.tasksLoading}
            error={crm.tasksError}
            pipeline={crm.pipeline}
            selectedConversation={crm.selectedConversation}
            onCreate={crm.createNewTask}
            onComplete={crm.completeTask}
          />
        {:else}
          <LeadTimeline timeline={crm.timeline} />
        {/if}
      </div>
    </div>
  </div>

  <Toast toasts={crm.toasts} />
</section>
