<script>
  import { studio } from "../state.svelte";
  import { connectSse } from "../sse";
  import StudioHeader from "./StudioHeader.svelte";
  import StudioLayout from "./StudioLayout.svelte";
  import WorkflowCanvas from "./WorkflowCanvas.svelte";
  import RunInspector from "./RunInspector.svelte";
  import JourneyBar from "./JourneyBar.svelte";
  import EventStream from "./EventStream.svelte";
  import RunHistory from "./RunHistory.svelte";
  import WhatsAppInbox from "./WhatsAppInbox.svelte";

  let disconnect = null;
  let filterType = $state("all");

  const sampleInput = "Necesito precio y ubicacion. Email: test@mail.com";

  const useSample = () => {
    studio.setInputText(sampleInput);
  };

  $effect(() => {
    if (typeof window === "undefined") return;
    studio.refreshRuns();
    disconnect = connectSse({
      onEvent: (evt) => {
        studio.pushSseEvent(evt);
        if (evt.type && evt.type.startsWith("ai_workflow.")) {
          studio.applySseEvent(evt);
        }
        // Also handle messaging for inbox
        if (evt.type && evt.type.startsWith("messaging.")) {
          studio.applySseEvent(evt);
        }
      },
      onMeta: studio.noteSseEvent,
      onStatus: studio.setConnectionStatus,
    });
    return () => {
      disconnect?.();
      disconnect = null;
    };
  });
</script>

<div
  class="studio-shell relative overflow-hidden rounded-[32px] border border-base-200 bg-gradient-to-br from-white via-slate-50 to-cyan-50 shadow-xl"
>
  <div
    class="pointer-events-none absolute -top-24 left-8 h-64 w-64 rounded-full bg-amber-200/40 blur-3xl"
  ></div>
  <div
    class="pointer-events-none absolute bottom-0 right-0 h-72 w-72 rounded-full bg-teal-200/40 blur-3xl"
  ></div>

  <div class="relative z-10 p-4 md:p-6">
    <StudioLayout>
      <StudioHeader
        slot="header"
        connectionStatus={studio.connectionStatus}
        onRefresh={studio.refreshRuns}
        onClear={studio.clearEvents}
      />

      <div slot="input" class="space-y-4 min-w-0">
        <div
          class="card overflow-hidden border border-base-200 bg-base-100/90 shadow-sm"
        >
          <div class="card-body gap-4 p-5">
            <div
              class="flex flex-wrap items-center justify-between gap-3 min-w-0"
            >
              <div>
                <p
                  class="text-xs uppercase tracking-[0.3em] text-slate-500 font-semibold"
                >
                  New run
                </p>
                <h3 class="text-lg font-semibold text-slate-900">
                  Input determinista
                </h3>
              </div>
              <div class="flex items-center gap-2 min-w-0">
                <button class="btn btn-ghost btn-sm" onclick={useSample}
                  >Sample</button
                >
                <button
                  class="btn btn-primary btn-sm"
                  onclick={studio.startRun}
                  disabled={studio.busy}
                >
                  {studio.busy ? "Running..." : "Start run"}
                </button>
              </div>
            </div>

            <textarea
              class="textarea textarea-bordered min-h-[120px] w-full text-sm leading-relaxed"
              placeholder="Describe la solicitud del cliente..."
              value={studio.inputText}
              oninput={(event) =>
                studio.setInputText(event.currentTarget.value)}
            ></textarea>

            <div
              class="flex flex-wrap items-center justify-between gap-2 min-w-0 text-xs text-neutral-500"
            >
              <span>Active run: {studio.activeRunId || "--"}</span>
              <span>{studio.activeInputLen} chars</span>
            </div>
          </div>
        </div>

        <WorkflowCanvas
          activeNodeId={studio.activeNodeId}
          activeRunId={studio.activeRunId}
          stepsByNodeId={studio.stepsByNodeId}
        />

        <RunHistory
          runs={studio.runs}
          selectedRunId={studio.activeRunId}
          activeRunId={studio.activeRunId}
          onSelect={studio.setActiveRunId}
          onRefresh={studio.refreshRuns}
          autoFocusNewest={studio.autoFocusNewest}
          setAutoFocusNewest={studio.setAutoFocusNewest}
        />
      </div>

      <RunInspector
        slot="inspector"
        run={studio.activeRun}
        events={studio.sseEvents}
        activeTicketId={studio.activeTicketId}
      />

      <div slot="events" class="space-y-4 min-w-0">
        <JourneyBar
          events={studio.sseEvents}
          activeRunId={studio.activeRunId}
          activeTicketId={studio.activeTicketId}
          activeFilter={filterType}
          onFilter={(type) => (filterType = type)}
        />
        <EventStream
          events={studio.sseEvents}
          sseConnected={studio.sseConnected}
          lastEventAt={studio.lastEventAt}
          eventCount={studio.eventCount}
          activeRunId={studio.activeRunId}
          activeTicketId={studio.activeTicketId}
          setActiveRunId={studio.setActiveRunId}
          setActiveTicketId={studio.setActiveTicketId}
          bind:filterType
        />
      </div>

      <WhatsAppInbox
        slot="inbox"
        messages={studio.inboundMessages}
        onUse={studio.setInputText}
      />
    </StudioLayout>
  </div>
</div>

<style>
  @import url("https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap");

  :global(.studio-shell) {
    font-family: "Outfit", "Segoe UI", system-ui, sans-serif;
  }
</style>
