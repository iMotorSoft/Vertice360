<script>
  import { onMount, onDestroy } from "svelte";
  import { URL_REST, URL_SSE } from "../../../../../global";
  import { connectSSE, parseSseData } from "../../../../../../lib/messaging/sse";

  const EVENT_TYPES = [
    "messaging.outbound",
    "messaging.inbound",
    "messaging.status",
    "conversation.message.new",
    "conversation.message.status",
  ];

  /** @type {'CONNECTING' | 'ONLINE' | 'ERROR'} */
  let status = $state("CONNECTING");
  let sseError = $state("");
  let eventLog = $state([]);
  let eventSeq = 0;
  /** @type {EventSource | null} */
  let source = null;

  let to = $state("");
  let text = $state("");
  let isSending = $state(false);
  let sendResult = $state(null);
  let sendError = $state("");

  const formatPayload = (payload) => {
    if (payload === undefined || payload === null) return "";
    if (typeof payload === "string") return payload;
    try {
      return JSON.stringify(payload, null, 2);
    } catch (err) {
      return String(payload);
    }
  };

  const shouldInclude = (event, parsed) => {
    if (parsed?.kind === "custom") {
      const value = parsed.value;
      if (value && typeof value === "object" && "provider" in value) {
        return value.provider === "gupshup";
      }
      return typeof parsed.name === "string" && parsed.name.startsWith("messaging.");
    }

    return typeof event?.type === "string" && event.type.startsWith("messaging.");
  };

  const appendEvent = (event) => {
    const parsed = parseSseData(event.data);
    if (!shouldInclude(event, parsed)) return;

    eventSeq += 1;
    const entry = {
      id: eventSeq,
      event: event.type || "message",
      receivedAt: new Date().toISOString(),
      parsed,
    };

    eventLog = [entry, ...eventLog].slice(0, 30);
  };

  const connect = () => {
    status = "CONNECTING";
    sseError = "";

    if (source) {
      source.close();
      source = null;
    }

    try {
      source = connectSSE(URL_SSE, {
        events: EVENT_TYPES,
        onEvent: appendEvent,
        onOpen: () => {
          status = "ONLINE";
        },
        onError: () => {
          status = "ERROR";
          sseError = "SSE connection error.";
        },
      });
    } catch (err) {
      status = "ERROR";
      sseError = err?.message ?? "Unable to open SSE connection.";
      source = null;
    }
  };

  const sendMessage = async () => {
    if (isSending) return;
    sendError = "";
    sendResult = null;
    isSending = true;

    try {
      const payload = { to: to.trim(), text: text.trim() };
      const response = await fetch(`${URL_REST}/api/demo/messaging/gupshup/whatsapp/send`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const contentType = response.headers.get("content-type") || "";
      const data = contentType.includes("application/json") ? await response.json() : await response.text();

      if (!response.ok) {
        sendError = typeof data === "string" ? data : formatPayload(data);
      } else {
        sendResult = data;
      }
    } catch (err) {
      sendError = err?.message ?? "Request failed.";
    } finally {
      isSending = false;
    }
  };

  const clearLog = () => {
    eventLog = [];
  };

  onMount(() => {
    connect();
  });

  onDestroy(() => {
    if (source) {
      source.close();
      source = null;
    }
  });
</script>

<div class="grid gap-6 md:grid-cols-2">
  <section class="card bg-base-100 shadow-sm border border-base-200">
    <div class="card-body space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="card-title text-base">SSE Connection Status</h2>
        <span
          class="badge"
          class:badge-success={status === "ONLINE"}
          class:badge-warning={status === "CONNECTING"}
          class:badge-error={status === "ERROR"}
        >
          {status}
        </span>
      </div>
      <p class="text-xs text-neutral-500">Endpoint: {URL_SSE}</p>
      <p class="text-xs text-neutral-500">
        Listening for messaging.inbound, messaging.status, conversation.message.new, conversation.message.status, message.
      </p>
      {#if sseError}
        <p class="text-xs text-error">{sseError}</p>
      {/if}
    </div>
  </section>

  <section class="card bg-base-100 shadow-sm border border-base-200">
    <div class="card-body space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="card-title text-base">Outbound Test (Send WhatsApp)</h2>
      </div>

      <label class="form-control w-full">
        <div class="label">
          <span class="label-text">To</span>
        </div>
        <input
          class="input input-bordered w-full"
          placeholder="e.g. 5215551234567"
          bind:value={to}
        />
      </label>

      <label class="form-control w-full">
        <div class="label">
          <span class="label-text">Text</span>
        </div>
        <textarea
          class="textarea textarea-bordered w-full"
          rows="4"
          placeholder="Hello from Gupshup WhatsApp lab"
          bind:value={text}
        ></textarea>
      </label>

      <div class="flex items-center gap-3">
        <button
          class="btn btn-primary"
          disabled={isSending || !to.trim() || !text.trim()}
          onclick={sendMessage}
        >
          {isSending ? "Sending..." : "Send"}
        </button>
        <span class="text-xs text-neutral-500">POST /api/demo/messaging/gupshup/whatsapp/send</span>
      </div>

      <div class="space-y-2">
        {#if sendError}
          <div class="text-xs text-error whitespace-pre-wrap">{sendError}</div>
        {:else if sendResult}
          <pre class="text-xs bg-base-200 rounded p-3 overflow-x-auto">{formatPayload(sendResult)}</pre>
        {:else}
          <p class="text-xs text-neutral-500">No response yet.</p>
        {/if}
      </div>
    </div>
  </section>

  <section class="card bg-base-100 shadow-sm border border-base-200 md:col-span-2">
    <div class="card-body space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="card-title text-base">Live Event Log (last 30)</h2>
        <button class="btn btn-ghost btn-xs" onclick={clearLog}>Clear</button>
      </div>

      <div class="space-y-3 max-h-[28rem] overflow-y-auto">
        {#if eventLog.length === 0}
          <p class="text-xs text-neutral-500">Waiting for SSE events...</p>
        {/if}

        {#each eventLog as entry (entry.id)}
          <div class="border border-base-200 rounded-lg p-3 bg-base-100">
            <div class="flex items-center justify-between">
              <span class="badge badge-outline">{entry.event}</span>
              <span class="text-xs text-neutral-500">{entry.receivedAt}</span>
            </div>

            {#if entry.parsed.kind === "custom"}
              <div class="mt-2 text-sm font-semibold">{entry.parsed.name}</div>
              <div class="text-xs text-neutral-500">
                Timestamp: {entry.parsed.timestamp ?? entry.receivedAt}
              </div>
              <pre class="mt-2 text-xs bg-base-200 rounded p-2 overflow-x-auto">{formatPayload(entry.parsed.value)}</pre>
            {:else}
              <pre class="mt-2 text-xs bg-base-200 rounded p-2 overflow-x-auto">{formatPayload(entry.parsed.value ?? entry.parsed.raw)}</pre>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  </section>
</div>
