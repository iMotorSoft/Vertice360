<!-- DEMO – Copiloto de inventario Vertice360 (chat sobre datos mock) -->
<script lang="ts">
  import { URL_REST } from "../../global";

  type ChatMessage = {
    role: "user" | "assistant";
    content: string;
    timestamp: string;
  };

  let prompt = $state("");
  let loading = $state(false);
  let error: string | null = $state(null);
  let messages = $state<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Soy el copiloto de inventario Vertice360 (demo). Preguntá por proyectos, inversores o reservas y cito los IDs.",
        timestamp: new Date().toISOString(),
    },
  ]);
  let messagesContainer: HTMLDivElement | null = null;

  const formatTime = (iso: string) =>
    new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });

  const sendMessage = async () => {
    const text = prompt.trim();
    if (!text || loading) return;
    error = null;

    const historyBeforeMessage = messages; // evitamos duplicar el prompt en history
    const userMessage: ChatMessage = { role: "user", content: text, timestamp: new Date().toISOString() };
    messages = [...messages, userMessage];
    prompt = "";
    loading = true;

    try {
      const res = await fetch(`${URL_REST}/api/demo/codex/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: text,
          history: historyBeforeMessage.map(({ role, content }) => ({ role, content })),
        }),
      });

      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status}: ${detail || "Error en el chat de demo"}`);
      }

      const data: { reply: string } = await res.json();
      messages = [
        ...messages,
        {
          role: "assistant",
          content: data.reply || "Sin respuesta del modelo.",
          timestamp: new Date().toISOString(),
        },
      ];
      requestAnimationFrame(() => {
        messagesContainer?.scrollTo({ top: 0, behavior: "smooth" });
      });
    } catch (err) {
      error = err instanceof Error ? err.message : "Error desconocido al consultar el chat.";
    } finally {
      loading = false;
    }
  };

  const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };
</script>

<div class="card bg-base-100 shadow-lg border border-emerald-100 lg:sticky lg:top-4">
  <div class="card-body space-y-4">
    <div class="flex items-start justify-between gap-2">
      <div>
        <p class="text-xs uppercase tracking-wide text-emerald-700 font-semibold">Copiloto de inventario</p>
        <h3 class="card-title text-lg">Chat sobre el inventario demo</h3>
        <p class="text-sm text-neutral-600">Consulta proyectos, inversores y operaciones de la demo.</p>
      </div>
      <span class="badge badge-outline badge-sm text-xs">Chat demo</span>
    </div>

    <div class="bg-emerald-50/60 border border-emerald-100 rounded-lg p-3 text-xs text-emerald-900">
      <p class="font-semibold">Contexto:</p>
      <p>Usamos datos ficticios del inventario demo y el modelo configurado en backend.</p>
      <p>Envía texto libre; el backend arma el prompt con los IDs del mock.</p>
    </div>

    <div
      class="border border-base-200 rounded-lg max-h-[60vh] min-h-[18rem] overflow-y-auto p-3 space-y-3 bg-base-100"
      bind:this={messagesContainer}
    >
      {#each [...messages].reverse() as msg, idx (msg.timestamp + idx)}
        <div class={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`} aria-live={idx === messages.length - 1 ? "polite" : "off"}>
          <div
            class={`max-w-[92%] rounded-xl px-3 py-2 text-sm ${
              msg.role === "user"
                ? "bg-emerald-600 text-emerald-50"
                : "bg-white border border-base-200 text-neutral-800 shadow-sm"
            }`}
          >
            <div class="flex items-center gap-2 mb-1">
              <span class="text-[11px] uppercase tracking-wide font-semibold">
                {msg.role === "user" ? "Vos" : "Copiloto"}
              </span>
              <span class="text-[10px] opacity-70">{formatTime(msg.timestamp)}</span>
            </div>
            <p class="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
          </div>
        </div>
      {/each}
    </div>

    {#if error}
      <div class="alert alert-error text-sm">
        <span>{error}</span>
      </div>
    {/if}

    <div class="space-y-2">
      <label class="text-sm font-semibold text-neutral-700">Escribe tu consulta</label>
      <textarea
        class="textarea textarea-bordered w-full text-sm"
        rows="3"
        bind:value={prompt}
        placeholder="Ej: ¿Qué inversor tiene una reserva en PZ-ALV-101?"
        on:keydown={handleKeydown}
      />
      <div class="flex items-center justify-between gap-3">
        <span class="text-xs text-neutral-500">Envia con Enter · Shift+Enter para salto de línea.</span>
        <button class="btn btn-primary btn-sm" on:click={sendMessage} disabled={loading || !prompt.trim()}>
          {#if loading}
            <span class="loading loading-spinner loading-xs"></span>
            Pensando...
          {:else}
            Enviar
          {/if}
        </button>
      </div>
    </div>
  </div>
</div>
