<script>
  let { tabs = [], active = null, onChange = () => {} } = $props();
</script>

<div class="tabs tabs-boxed w-full min-w-0">
  {#each tabs as tab}
    <button
      class={`tab flex-1 min-w-0 ${active === tab.key ? "tab-active" : ""}`}
      on:click={() => onChange(tab.key)}
      type="button"
    >
      {tab.label}
    </button>
  {/each}
</div>
