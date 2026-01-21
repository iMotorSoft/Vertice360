<script>
  import ResponsiveTabs from "./ResponsiveTabs.svelte";

  let activeTab = $state("input");
  const tabs = [
    { key: "input", label: "Input" },
    { key: "inspector", label: "Inspector" },
    { key: "events", label: "Events" },
    { key: "inbox", label: "Inbox" },
  ];
</script>

<div class="space-y-5 min-w-0">
  <slot name="header" />

  <div class="hidden lg:grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,420px)] gap-4 min-w-0">
    <div class="min-w-0 space-y-4">
      <slot name="input" />
    </div>
    <div class="min-w-0">
      <slot name="inspector" />
    </div>
    <div class="min-w-0 space-y-4">
      <slot name="events" />
      <slot name="inbox" />
    </div>
  </div>

  <div class="hidden md:block lg:hidden min-w-0">
    <div class="grid md:grid-cols-2 gap-4 min-w-0">
      <div class="min-w-0 space-y-4">
        <slot name="input" />
      </div>
      <div class="min-w-0">
        <slot name="inspector" />
      </div>
    </div>
    <div class="mt-4 min-w-0 space-y-4">
      <slot name="events" />
      <slot name="inbox" />
    </div>
  </div>

  <div class="md:hidden space-y-4 min-w-0">
    <ResponsiveTabs tabs={tabs} active={activeTab} onChange={(next) => (activeTab = next)} />
    {#if activeTab === "input"}
      <div class="min-w-0">
        <slot name="input" />
      </div>
    {:else if activeTab === "inspector"}
      <div class="min-w-0">
        <slot name="inspector" />
      </div>
    {:else if activeTab === "inbox"}
      <div class="min-w-0">
        <slot name="inbox" />
      </div>
    {:else}
      <div class="min-w-0">
        <slot name="events" />
      </div>
    {/if}
  </div>
</div>
