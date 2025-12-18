<script lang="ts">
  import { onMount } from "svelte";
  import { relativeTime } from "../../../lib/crm/time";

  type Message = {
    id: string;
    conversationId: string;
    sender: string;
    text: string;
    ts: string;
    status?: string;
  };

  type Conversation = {
    id: string;
    leadId: string;
    channel: string;
    subject: string;
    messages?: Message[];
  };

  type ComponentProps = {
    conversation?: Conversation | null;
    loading?: boolean;
    onSend?: (text: string) => Promise<void> | void;
    placeholder?: string;
  };

  let { conversation = null, loading = false, onSend, placeholder = "Enviar mensaje" } = $props<ComponentProps>();

  let draft = $state("");
  let sending = $state(false);
  let threadEl: HTMLDivElement | null = null;
  let autoStick = $state(true);

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

  const scrollToBottom = () => {
    if (threadEl) {
      threadEl.scrollTo({ top: threadEl.scrollHeight, behavior: "smooth" });
    }
  };

  $effect(() => {
    conversation?.messages?.length;
    queueMicrotask(() => {
      if (autoStick) scrollToBottom();
    });
  });

  onMount(() => {
    scrollToBottom();
  });

  const send = async () => {
    if (!draft.trim()) return;
    sending = true;
    try {
      await onSend?.(draft);
      draft = "";
      autoStick = true;
      scrollToBottom();
    } finally {
      sending = false;
    }
  };

  const onScroll = () => {
    if (!threadEl) return;
    const nearBottom = threadEl.scrollTop + threadEl.clientHeight >= threadEl.scrollHeight - 160;
    autoStick = nearBottom;
  };
</script>

<div class="flex flex-col h-full">
  <div class="sticky top-0 z-10 border-b bg-base-100/95 backdrop-blur p-4 flex items-center justify-between">
    <div class="space-y-1">
      <p class="text-xs uppercase tracking-wide text-slate-500 font-semibold">Conversación</p>
      <div class="flex items-center gap-2">
        <h3 class="text-xl font-semibold text-slate-900">{conversation?.subject}</h3>
        {#if conversation}
          <span class={`badge ${badgeForChannel(conversation.channel)} capitalize`}>{conversation.channel}</span>
        {/if}
      </div>
      <p class="text-sm text-slate-500">Lead: {conversation?.leadId}</p>
    </div>
  </div>

  {#if loading}
    <div class="p-6 space-y-4">
      {#each Array(5) as _, idx}
        <div class="flex gap-3 items-start animate-pulse" aria-label={`message-skeleton-${idx}`}>
          <div class="h-8 w-8 rounded-full bg-base-200"></div>
          <div class="flex-1 space-y-2">
            <div class="h-3 w-1/3 bg-base-200 rounded"></div>
            <div class="h-3 w-2/3 bg-base-200 rounded"></div>
          </div>
        </div>
      {/each}
    </div>
  {:else if conversation}
    <div class="flex-1 overflow-y-auto p-4 space-y-3" bind:this={threadEl} on:scroll={onScroll}>
      {#each conversation.messages ?? [] as msg (msg.id)}
        <div class={`flex ${msg.sender === "agent" ? "justify-end" : "justify-start"}`}>
          <div
            class={`max-w-[75%] rounded-2xl px-4 py-3 shadow-sm ${
              msg.sender === "agent" ? "bg-primary text-primary-content" : "bg-base-200 text-slate-900"
            }`}
          >
            <p class="text-sm leading-relaxed whitespace-pre-line">{msg.text}</p>
            <div class="mt-2 flex items-center gap-2 text-xs opacity-80">
              <span>{relativeTime(msg.ts)}</span>
              {#if msg.status}
                <span class="inline-flex items-center gap-1">
                  <span
                    class={`h-2 w-2 rounded-full ${
                      msg.status === "read" ? "bg-success" : msg.status === "delivered" ? "bg-info" : "bg-slate-400"
                    }`}
                  ></span>
                  {msg.status}
                </span>
              {/if}
            </div>
          </div>
        </div>
      {/each}
    </div>

    <div class="border-t bg-base-100 p-4">
      <label class="block text-sm text-slate-600 mb-2">Responder</label>
      <div class="space-y-2">
        <textarea
          class="textarea textarea-bordered w-full"
          placeholder={placeholder}
          bind:value={draft}
          rows="3"
          on:keydown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        ></textarea>
        <div class="flex items-center justify-between">
          <p class="text-xs text-slate-500">Shift+Enter para salto de línea</p>
          <button class="btn btn-primary btn-sm" on:click={send} disabled={sending}>
            {#if sending}
              <span class="loading loading-spinner loading-xs"></span>
            {/if}
            Enviar
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>
