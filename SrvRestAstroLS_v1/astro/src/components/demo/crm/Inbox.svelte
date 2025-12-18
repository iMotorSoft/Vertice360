<script lang="ts">
  type Conversation = {
    id: string;
    leadId: string;
    channel: string;
    subject: string;
    messages?: { id: string; sender: string; text: string; ts: string; status?: string }[];
  };

  export let conversations: Conversation[] = [];
  export let loading = false;
  export let error: string | null = null;
  export let selectedId: string | null = null;
  export let search = "";
  export let channelFilter = "all";
  export let onSelect: (id: string) => void;
  export let onSearch: (value: string) => void;
  export let onFilter: (value: string) => void;

  const channels = ["all", "whatsapp", "facebook", "instagram", "email", "webchat"];

  const badgeForChannel = (channel: string) => {
    const map: Record<string, string> = {
      whatsapp: "badge-success",
      facebook: "badge-info",
      instagram: "badge-secondary",
      email: "badge-neutral",
      webchat: "badge-primary",
    };
    return map[channel] ?? "badge-ghost";
  };

  const filtered = () => {
    const lower = search.toLowerCase();
    return (conversations ?? [])
      .filter((c) => channelFilter === "all" || c.channel === channelFilter)
      .filter(
        (c) =>
          !lower ||
          c.subject.toLowerCase().includes(lower) ||
          c.leadId.toLowerCase().includes(lower) ||
          c.messages?.some((m) => m.text.toLowerCase().includes(lower)),
      )
      .sort((a, b) => {
        const lastA = a.messages?.[a.messages.length - 1];
        const lastB = b.messages?.[b.messages.length - 1];
        return (lastB ? new Date(lastB.ts).getTime() : 0) - (lastA ? new Date(lastA.ts).getTime() : 0);
      });
  };

  const preview = (c: Conversation) => {
    const last = c.messages?.[c.messages.length - 1];
    if (!last) return "Sin mensajes aún";
    return `${last.sender === "agent" ? "Tú: " : ""}${last.text}`;
  };

  const isUnread = (c: Conversation) => {
    const last = c.messages?.[c.messages.length - 1];
    if (!last) return false;
    return last.sender === "lead" && last.status !== "read";
  };
</script>

<div class="flex items-center justify-between gap-2">
  <div>
    <p class="text-xs uppercase tracking-wide text-slate-500 font-semibold">Inbox</p>
    <h3 class="text-lg font-semibold text-slate-900">Conversaciones</h3>
  </div>
  {#if loading}
    <span class="loading loading-spinner loading-sm text-primary" aria-label="Cargando inbox"></span>
  {/if}
</div>

<div class="form-control mt-3">
  <label class="input input-bordered flex items-center gap-2">
    <span class="icon-[heroicons-magnifying-glass-20-solid] text-slate-400"></span>
    <input
      type="text"
      class="grow"
      placeholder="Buscar por lead, asunto o mensaje"
      value={search}
      on:input={(e) => onSearch?.(e.currentTarget.value)}
    />
  </label>
</div>

<div class="mt-3 flex flex-wrap gap-2">
  {#each channels as ch}
    <button
      class={`btn btn-xs rounded-full ${channelFilter === ch ? "btn-primary" : "btn-ghost"}`}
      on:click={() => onFilter?.(ch)}
    >
      {ch === "all" ? "Todos" : ch}
    </button>
  {/each}
</div>

{#if error}
  <div class="alert alert-error mt-4 text-sm">
    <span>{error}</span>
  </div>
{:else}
  <div class="mt-4 space-y-2">
    {#if loading}
      {#each Array(4) as _, idx}
        <div class="animate-pulse rounded-xl border border-base-200 p-3" aria-label={`skeleton-${idx}`}>
          <div class="h-4 w-1/3 bg-base-200 rounded"></div>
          <div class="mt-2 h-3 w-2/3 bg-base-200 rounded"></div>
        </div>
      {/each}
    {:else if filtered().length === 0}
      <div class="text-sm text-slate-500 py-6 text-center">Sin conversaciones para este filtro.</div>
    {:else}
      {#each filtered() as conv (conv.id)}
        <button
          class={`w-full text-left rounded-2xl border p-3 transition hover:-translate-y-[1px] hover:border-primary/40 hover:shadow ${
            selectedId === conv.id ? "border-primary/70 bg-primary/5" : "border-base-200"
          }`}
          on:click={() => onSelect?.(conv.id)}
        >
          <div class="flex items-start gap-3">
            <div class="avatar placeholder">
              <div class="bg-primary/10 text-primary font-semibold w-10 rounded-full">
                <span>{conv.leadId?.slice(0, 2).toUpperCase()}</span>
              </div>
            </div>
            <div class="min-w-0 flex-1 space-y-1">
              <div class="flex items-center gap-2">
                <p class="font-semibold text-slate-900 line-clamp-1">{conv.subject}</p>
                <span class={`badge badge-xs ${badgeForChannel(conv.channel)} capitalize`}>{conv.channel}</span>
                {#if isUnread(conv)}
                  <span class="h-2 w-2 rounded-full bg-primary"></span>
                {/if}
              </div>
              <p class="text-sm text-slate-600 line-clamp-2">{preview(conv)}</p>
            </div>
          </div>
        </button>
      {/each}
    {/if}
  </div>
{/if}

