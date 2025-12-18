<script lang="ts">
  import { relativeTime, formatDateTime } from "../../../lib/crm/time";

  type TimelineItem = {
    id: string;
    ts: number;
    type: string;
    text?: string;
    actor?: string;
    meta?: string;
  };

  export let timeline: TimelineItem[] = [];

  const iconForType = (type: string) => {
    if (type.startsWith("message")) return "icon-[heroicons-chat-bubble-left-right-20-solid]";
    if (type === "deal") return "icon-[heroicons-arrow-right-circle-20-solid]";
    if (type === "task") return "icon-[heroicons-check-circle-20-solid]";
    return "icon-[heroicons-bell-alert-20-solid]";
  };

  const toneForType = (type: string) => {
    if (type.startsWith("message")) return "bg-sky-100 text-sky-700";
    if (type === "deal") return "bg-amber-100 text-amber-700";
    if (type === "task") return "bg-emerald-100 text-emerald-700";
    return "bg-slate-100 text-slate-700";
  };
</script>

<div class="p-4 space-y-4">
  <div>
    <p class="text-xs uppercase tracking-wide text-slate-500 font-semibold">Timeline</p>
    <h3 class="text-lg font-semibold text-slate-900">Actividad reciente</h3>
  </div>

  {#if timeline.length === 0}
    <p class="text-sm text-slate-500">Sin eventos para este lead aún.</p>
  {:else}
    <div class="space-y-3">
      {#each timeline as item (item.id)}
        <div class="flex items-start gap-3">
          <div class={`rounded-full p-2 shrink-0 ${toneForType(item.type)}`}>
            <span class={iconForType(item.type)}></span>
          </div>
          <div class="flex-1 rounded-2xl border border-base-200 p-3 bg-base-100/70 shadow-sm">
            <div class="flex items-center justify-between">
              <p class="font-semibold text-slate-900">{item.text ?? item.type}</p>
              <span class="text-xs text-slate-500">{relativeTime(item.ts)}</span>
            </div>
            <p class="text-xs text-slate-500 mt-1">{formatDateTime(item.ts)}</p>
            {#if item.actor}
              <p class="text-xs text-slate-600 mt-1">Actor: {item.actor}</p>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

