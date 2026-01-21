<script>
  import { formatTime, shortId } from "../types";

  let { messages = [], onUse = () => {} } = $props();

  const hasText = (value) =>
    typeof value === "string" && value.trim().length > 0;
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
          WhatsApp Inbox
        </p>
        <h3 class="text-lg font-semibold text-slate-900">Mensajes entrantes</h3>
      </div>
      <div class="text-xs text-neutral-500">{messages.length} inbound</div>
    </div>

    <div class="space-y-3 max-h-[45vh] overflow-y-auto pr-1">
      {#if messages.length === 0}
        <div
          class="rounded-2xl border border-dashed border-base-300 p-5 text-sm text-neutral-500"
        >
          Esperando mensajes inbound de WhatsApp.
        </div>
      {:else}
        {#each messages as message}
          <div class="rounded-2xl border border-base-200 bg-white/90 p-4">
            <div
              class="flex flex-wrap items-center justify-between gap-2 min-w-0"
            >
              <div class="text-xs text-neutral-500">
                {formatTime(message.timestamp)}
              </div>
              <div class="text-xs text-neutral-400">
                {shortId(message.messageId || message.correlationId)}
              </div>
            </div>
            <p class="mt-1 text-xs text-neutral-500">
              From: {message.from || "--"}
            </p>
            <p class="mt-1 text-sm font-semibold text-slate-900 break-words">
              {message.text || "Sin texto"}
            </p>
            <div class="mt-3 flex justify-end">
              <button
                class="btn btn-ghost btn-xs"
                type="button"
                disabled={!hasText(message.text)}
                onclick={() => onUse(message.text)}
              >
                Use as input
              </button>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>
</div>
