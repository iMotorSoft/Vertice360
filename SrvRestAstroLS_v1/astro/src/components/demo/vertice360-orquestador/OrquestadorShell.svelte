<script>
  import { onMount } from "svelte";
  import Landing from "./Landing.svelte";
  import OrquestadorApp from "./OrquestadorApp.svelte";

  let ready = $state(false);
  let clientPhone = $state("");

  const readClientPhone = () => {
    if (typeof window === "undefined") return "";
    return (new URLSearchParams(window.location.search).get("cliente") ?? "").trim();
  };

  const syncFromUrl = () => {
    clientPhone = readClientPhone();
    ready = true;
  };

  onMount(() => {
    syncFromUrl();
    window.addEventListener("popstate", syncFromUrl);
    return () => {
      window.removeEventListener("popstate", syncFromUrl);
    };
  });
</script>

{#if !ready}
  <section class="mx-auto max-w-3xl">
    <div class="alert alert-info">
      <span>Cargando...</span>
    </div>
  </section>
{:else if clientPhone}
  {#key clientPhone}
    <OrquestadorApp clientPhone={clientPhone} />
  {/key}
{:else}
  <Landing />
{/if}
