<script>
  let {
    open = false,
    cliente = "",
    mode = "proponer",
    initialAdvisor = "",
    initialOption1 = "",
    initialOption2 = "",
    initialOption3 = "",
    initialMessage = "",
    onClose = () => {},
    onSubmit = () => {},
  } = $props();

  const DEFAULTS = {
    advisor: "Asesor Demo",
    option1: "Lunes 10:00",
    option2: "Martes 17:30",
    option3: "",
  };

  let asesor = $state(DEFAULTS.advisor);
  let opcion1 = $state(DEFAULTS.option1);
  let opcion2 = $state(DEFAULTS.option2);
  let opcion3 = $state(DEFAULTS.option3);
  let mensaje = $state("Hola, te comparto opciones para coordinar una visita.");
  let submitting = $state(false);

  const getModeConfig = (currentMode) => {
    if (currentMode === "ver_propuesta") {
      return {
        title: "Ver o reenviar propuesta",
        submitLabel: "Reenviar propuesta",
        helperText:
          "Podés reenviar o ajustar las opciones propuestas para confirmar la visita.",
        defaultMessage:
          "Te reenvío las opciones de visita para que podamos confirmar.",
      };
    }
    if (currentMode === "reagendar") {
      return {
        title: "Reagendar visita",
        submitLabel: "Enviar reprogramación",
        helperText: "Actualizá los horarios para coordinar una nueva visita.",
        defaultMessage: "Te comparto nuevos horarios para reagendar la visita.",
      };
    }
    return {
      title: "Proponer visita",
      submitLabel: "Enviar opciones",
      helperText:
        "Compartí opciones de día y horario para avanzar con la visita.",
      defaultMessage: "Hola, te comparto opciones para coordinar una visita.",
    };
  };

  $effect(() => {
    if (!open) return;
    const modeConfig = getModeConfig(mode);
    asesor = String(initialAdvisor || "").trim() || DEFAULTS.advisor;
    opcion1 = String(initialOption1 || "").trim() || DEFAULTS.option1;
    opcion2 = String(initialOption2 || "").trim() || DEFAULTS.option2;
    opcion3 = String(initialOption3 || "").trim() || DEFAULTS.option3;
    mensaje = String(initialMessage || "").trim() || modeConfig.defaultMessage;
    submitting = false;
  });

  const handleClose = () => {
    if (submitting) return;
    onClose();
  };

  const handleSend = async () => {
    if (submitting) return;
    submitting = true;
    try {
      await onSubmit({
        cliente,
        asesor,
        opcion1,
        opcion2,
        opcion3,
        mensaje,
      });
      onClose();
    } finally {
      submitting = false;
    }
  };
</script>

<dialog
  class={`modal ${open ? "modal-open" : ""}`}
  aria-label="Proponer visita"
>
  <div class="modal-box relative w-11/12 max-w-xl space-y-4 p-6">
    <button
      type="button"
      class="btn btn-sm min-h-11 md:btn-xs md:min-h-[28px] hover:bg-gray-200 rounded-full p-2 absolute right-0 top-2"
      aria-label="Cerrar modal de visita"
      onclick={handleClose}
      disabled={submitting}
    >
      ✕
    </button>
    <h1 class="">
      {getModeConfig(mode).title}
    </h1>
    <p class="text-sm md:text-base text-slate-600 font-medium">
      Cliente: <span class="font-medium">{cliente || "Sin cliente"}</span>
    </p>
    <p class="text-sm md:text-base text-slate-500">
      {getModeConfig(mode).helperText}
    </p>

    <ul class="mt-6 space-y-4">
      <li class="flex flex-col gap-1">
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="flex items-center gap-2 px-1">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-slate-400"
            ><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" /><circle
              cx="12"
              cy="7"
              r="4"
            /></svg
          >
          <span
            class="text-xs font-semibold uppercase tracking-wider text-slate-500"
            >Asesor</span
          >
        </label>
        <input
          class="input input-bordered w-full bg-slate-50 focus:bg-white transition-colors"
          type="text"
          placeholder="Nombre del asesor"
          bind:value={asesor}
          disabled={submitting}
        />
      </li>

      <li class="flex flex-col gap-1">
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="flex items-center gap-2 px-1">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-slate-400"
            ><rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line
              x1="16"
              y1="2"
              x2="16"
              y2="6"
            /><line x1="8" y1="2" x2="8" y2="6" /><line
              x1="3"
              y1="10"
              x2="21"
              y2="10"
            /></svg
          >
          <span
            class="text-xs font-semibold uppercase tracking-wider text-slate-500"
            >Opción 1</span
          >
        </label>
        <input
          class="input input-bordered w-full bg-slate-50 focus:bg-white transition-colors"
          type="text"
          placeholder="Día y hora sugerida"
          bind:value={opcion1}
          disabled={submitting}
        />
      </li>

      <li class="flex flex-col gap-1">
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="flex items-center gap-2 px-1">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-slate-400"
            ><rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line
              x1="16"
              y1="2"
              x2="16"
              y2="6"
            /><line x1="8" y1="2" x2="8" y2="6" /><line
              x1="3"
              y1="10"
              x2="21"
              y2="10"
            /></svg
          >
          <span
            class="text-xs font-semibold uppercase tracking-wider text-slate-500"
            >Opción 2</span
          >
        </label>
        <input
          class="input input-bordered w-full bg-slate-50 focus:bg-white transition-colors"
          type="text"
          placeholder="Otra alternativa"
          bind:value={opcion2}
          disabled={submitting}
        />
      </li>

      <li class="flex flex-col gap-1">
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="flex items-center gap-2 px-1">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-slate-400"
            ><rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line
              x1="16"
              y1="2"
              x2="16"
              y2="6"
            /><line x1="8" y1="2" x2="8" y2="6" /><line
              x1="3"
              y1="10"
              x2="21"
              y2="10"
            /></svg
          >
          <span
            class="text-xs font-semibold uppercase tracking-wider text-slate-500"
            >Opción 3 (opcional)</span
          >
        </label>
        <input
          class="input input-bordered w-full bg-slate-50 focus:bg-white transition-colors"
          type="text"
          placeholder="Opcional"
          bind:value={opcion3}
          disabled={submitting}
        />
      </li>

      <li class="flex flex-col gap-1">
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="flex items-center gap-2 px-1">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            class="text-slate-400"
            ><path
              d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
            /></svg
          >
          <span
            class="text-xs font-semibold uppercase tracking-wider text-slate-500"
            >Mensaje</span
          >
        </label>
        <textarea
          class="textarea textarea-bordered min-h-24 w-full bg-slate-50 focus:bg-white transition-colors p-3"
          placeholder="Mensaje para el cliente..."
          bind:value={mensaje}
          disabled={submitting}
        ></textarea>
      </li>
    </ul>

    <div class="modal-action justify-between">
      <button
        type="button"
        class="btn btn-secondary min-h-11"
        onclick={handleClose}
        disabled={submitting}>Cancelar</button
      >
      <button
        type="button"
        class="btn btn-primary min-h-11"
        onclick={handleSend}
        disabled={submitting}
        >{submitting ? "Enviando..." : getModeConfig(mode).submitLabel}</button
      >
    </div>
  </div>

  <form method="dialog" class="modal-backdrop">
    <button type="button" onclick={handleClose}>close</button>
  </form>
</dialog>
