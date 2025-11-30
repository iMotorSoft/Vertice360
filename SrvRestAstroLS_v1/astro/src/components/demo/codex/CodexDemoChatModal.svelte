<!-- DEMO – Botón que abre el chat en modal pantalla completa -->
<script lang="ts">
  import CodexDemoChat from "./CodexDemoChat.svelte";

  let modalEl: HTMLDialogElement | null = null;

  const openModal = () => {
    modalEl?.showModal();
  };

  const closeModal = () => {
    modalEl?.close();
  };
</script>

<div class="flex items-center justify-between gap-3 bg-base-100 border border-emerald-100 rounded-xl p-3 shadow-sm">
  <span class="badge badge-ghost">Dash</span>
  <button class="btn btn-primary btn-sm" on:click={openModal}>Chat</button>
</div>

<dialog class="modal" bind:this={modalEl}>
  <div class="modal-box w-11/12 max-w-5xl h-[85vh] p-0 overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 border-b border-base-200 bg-base-100">
      <div>
        <p class="text-xs uppercase tracking-wide text-neutral-500 font-semibold">Copiloto de inventario</p>
        <h3 class="text-lg font-semibold text-neutral-900">Chat sobre el inventario demo</h3>
        <p class="text-xs text-neutral-500">Responde con IDs y datos ficticios para pruebas.</p>
      </div>
      <button class="btn btn-ghost btn-sm" on:click={closeModal} aria-label="Cerrar chat">✕</button>
    </div>
    <div class="flex-1 overflow-hidden p-3 bg-base-50">
      <CodexDemoChat />
    </div>
  </div>
  <form method="dialog" class="modal-backdrop">
    <button aria-label="Cerrar">close</button>
  </form>
</dialog>
