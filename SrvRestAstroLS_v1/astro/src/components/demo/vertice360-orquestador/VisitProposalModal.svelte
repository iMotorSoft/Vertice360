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
        helperText: "Podés reenviar o ajustar las opciones propuestas para confirmar la visita.",
        defaultMessage: "Te reenvío las opciones de visita para que podamos confirmar.",
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
      helperText: "Compartí opciones de día y horario para avanzar con la visita.",
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

<dialog class={`modal ${open ? "modal-open" : ""}`} aria-label="Proponer visita">
  <div class="modal-box relative w-11/12 max-w-xl">
    <button
      type="button"
      class="btn btn-ghost btn-sm absolute right-2 top-2"
      aria-label="Cerrar modal de visita"
      onclick={handleClose}
      disabled={submitting}
    >
      ✕
    </button>
    <h3 class="text-lg font-semibold text-slate-900">{getModeConfig(mode).title}</h3>
    <p class="text-sm text-slate-600 mt-1">
      Cliente: <span class="font-medium">{cliente || "Sin cliente"}</span>
    </p>
    <p class="text-xs text-slate-500 mt-1">{getModeConfig(mode).helperText}</p>

    <div class="mt-4 space-y-3">
      <label class="form-control w-full">
        <span class="label-text text-sm">Asesor</span>
        <input class="input input-bordered min-h-11" type="text" bind:value={asesor} disabled={submitting} />
      </label>

      <label class="form-control w-full">
        <span class="label-text text-sm">Opción 1 (día/hora)</span>
        <input class="input input-bordered min-h-11" type="text" bind:value={opcion1} disabled={submitting} />
      </label>

      <label class="form-control w-full">
        <span class="label-text text-sm">Opción 2 (día/hora)</span>
        <input class="input input-bordered min-h-11" type="text" bind:value={opcion2} disabled={submitting} />
      </label>

      <label class="form-control w-full">
        <span class="label-text text-sm">Opción 3 (opcional)</span>
        <input class="input input-bordered min-h-11" type="text" bind:value={opcion3} disabled={submitting} />
      </label>

      <label class="form-control w-full">
        <span class="label-text text-sm">Mensaje</span>
        <textarea class="textarea textarea-bordered min-h-24" bind:value={mensaje} disabled={submitting}></textarea>
      </label>
    </div>

    <div class="modal-action">
      <button type="button" class="btn btn-ghost min-h-11" onclick={handleClose} disabled={submitting}>Cancelar</button>
      <button type="button" class="btn btn-primary min-h-11" onclick={handleSend} disabled={submitting}
        >{submitting ? "Enviando..." : getModeConfig(mode).submitLabel}</button
      >
    </div>
  </div>

  <form method="dialog" class="modal-backdrop">
    <button type="button" onclick={handleClose}>close</button>
  </form>
</dialog>
