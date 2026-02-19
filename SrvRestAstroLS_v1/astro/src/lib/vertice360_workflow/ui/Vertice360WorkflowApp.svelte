<script>
  import { URL_FONT_SPACE_GROTESK } from "../../../components/global.js";
  import { onDestroy, onMount } from "svelte";
  import { workflow } from "../state.svelte";
  import { connectWorkflowSSE } from "../sse";
  import Inbox from "./Inbox.svelte";
  import LiveEventLog from "./LiveEventLog.svelte";
  import TicketDrawer from "./TicketDrawer.svelte";
  import TopBar from "./TopBar.svelte";

  let nowMs = $state(Date.now());
  let disconnect = null;
  let clockId = null;

  onMount(() => {
    workflow.init();
    disconnect = connectWorkflowSSE({
      onEvent: workflow.applyEvent,
      onStatus: workflow.setSseConnected,
    });
    clockId = setInterval(() => {
      nowMs = Date.now();
    }, 1000);
  });

  onDestroy(() => {
    disconnect?.();
    workflow.teardown();
    if (clockId) clearInterval(clockId);
  });

  const toneClass = (tone) => {
    if (tone === "error") return "alert-error";
    if (tone === "warning") return "alert-warning";
    if (tone === "success") return "alert-success";
    return "alert-info";
  };
</script>

<svelte:head>
  <link rel="stylesheet" href={URL_FONT_SPACE_GROTESK} />
</svelte:head>

<div class="vertice360-workflow-app relative overflow-hidden rounded-[32px] border border-base-200 bg-gradient-to-br from-white via-white to-slate-50 shadow-xl">
  <div class="pointer-events-none absolute -top-20 right-0 h-56 w-56 rounded-full bg-primary/10 blur-3xl"></div>
  <div class="pointer-events-none absolute -bottom-24 left-10 h-64 w-64 rounded-full bg-secondary/15 blur-3xl"></div>

  <div class="relative z-10 space-y-5 p-4 md:p-6">
    <TopBar
      connected={workflow.sse.connected}
      onReset={workflow.resetDemo}
      onRefresh={workflow.refreshTickets}
    />

    <div class="grid gap-4 xl:grid-cols-[320px,1fr]">
      <div class="card rounded-3xl border border-base-200 bg-base-100/90 shadow-sm">
        <div class="card-body p-4">
          <Inbox
            tickets={workflow.tickets}
            loading={workflow.ticketsLoading}
            error={workflow.ticketsError}
            selectedId={workflow.selectedTicketId}
            search={workflow.search}
            onSearch={workflow.setSearch}
            onSelect={workflow.selectTicket}
            onRetry={workflow.refreshTickets}
            nowMs={nowMs}
          />
        </div>
      </div>

      <div class="card rounded-3xl border border-base-200 bg-base-100/90 shadow-sm min-h-[70vh]">
        <div class="card-body p-0">
          <TicketDrawer
            ticket={workflow.selectedTicket}
            loading={workflow.detailLoading}
            error={workflow.detailError}
            onRetry={() => workflow.fetchTicketDetail(workflow.selectedTicketId, true)}
            onAssign={() => workflow.assignAdmin(workflow.selectedTicketId)}
            onRequestDocs={() => workflow.requestDocs(workflow.selectedTicketId)}
            onReceiveDocs={() => workflow.receiveDocs(workflow.selectedTicketId)}
            onClose={() => workflow.closeWithDocs(workflow.selectedTicketId)}
            onEscalate={() => workflow.escalateTicket(workflow.selectedTicketId)}
            onSimulateBreach={(slaType) => workflow.simulateBreach(workflow.selectedTicketId, slaType)}
            nowMs={nowMs}
          />
        </div>
      </div>
    </div>

    <LiveEventLog
      events={workflow.liveEvents}
      filters={workflow.filters}
      selectedTicketId={workflow.selectedTicketId}
      onFilterChange={workflow.setFilters}
      onCopy={(message) => workflow.addToast(message, "success")}
      nowMs={nowMs}
    />
  </div>

  {#if workflow.toasts.length > 0}
    <div class="toast toast-top toast-end z-50">
      {#each workflow.toasts as toast (toast.id)}
        <div class={`alert ${toneClass(toast.tone)} shadow-lg`}>
          <span>{toast.message}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  :global(.vertice360-workflow-app) {
    font-family: "Space Grotesk", "Inter", system-ui, sans-serif;
  }

  :global(.animate-fade-slide) {
    animation: fadeSlide 0.35s ease-out;
  }

  :global(.animate-rise) {
    animation: rise 0.3s ease-out both;
  }

  @keyframes fadeSlide {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>
