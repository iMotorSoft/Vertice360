<script>
  const demoPhoneHuman = "+4526325250";
  const demoPhoneWa = "4526325250";
  const waText = "OBRA_PALERMO_01";
  const waUrl = `https://wa.me/${demoPhoneWa}/?text=${encodeURIComponent(waText)}`;
</script>

<section class="mx-auto max-w-3xl space-y-6">
  <header class="space-y-2">
    <p class="text-xs uppercase tracking-[0.25em] text-emerald-700 font-semibold">Vertice360 Demo</p>
    <h1 class="text-2xl md:text-3xl font-bold text-slate-900">Vertice360 Orquestador</h1>
    <p class="text-sm md:text-base text-slate-600">
      Orquestá tus leads por WhatsApp, automatizá el seguimiento y tené control total: del anuncio al cierre.
    </p>
  </header>

  <div class="card border border-base-300 bg-base-100 shadow-sm">
    <div class="card-body gap-4">
      <p class="text-sm md:text-base text-slate-700">Para iniciar la demo, enviá un WhatsApp a:</p>
      <p class="text-2xl font-semibold tracking-wide text-slate-900">{demoPhoneHuman}</p>
      <a
        href={waUrl}
        target="_blank"
        rel="noreferrer"
        class="btn w-full min-h-11 md:w-auto border-0 bg-[#25D366] text-white hover:bg-[#1EBE5D] inline-flex items-center justify-center gap-2"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 32 32"
          class="h-4 w-4 fill-current"
          aria-hidden="true"
        >
          <path
            d="M19.1 17.2c-.3-.2-1.7-.8-1.9-.9-.3-.1-.5-.2-.8.2-.2.3-.9.9-1.1 1.1-.2.2-.4.2-.7.1-.3-.2-1.3-.5-2.5-1.6-.9-.8-1.5-1.8-1.7-2.1-.2-.3 0-.5.1-.7.1-.1.3-.3.4-.5.1-.1.2-.3.3-.5.1-.2 0-.4 0-.5 0-.1-.8-1.9-1.1-2.6-.3-.7-.6-.6-.8-.6h-.7c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.3 0 1.3 1 2.6 1.1 2.8.1.2 1.9 3 4.7 4.2 2.8 1.2 2.8.8 3.4.8.6 0 1.9-.8 2.2-1.5.3-.8.3-1.4.2-1.5-.1-.2-.3-.2-.6-.4z"
          ></path>
          <path
            d="M16 3C8.8 3 3 8.8 3 16c0 2.3.6 4.5 1.8 6.4L3 29l6.8-1.8c1.8 1 3.9 1.5 6.2 1.5 7.2 0 13-5.8 13-13S23.2 3 16 3zm0 23.4c-2 0-4-.5-5.7-1.5l-.4-.2-4 1 1.1-3.9-.3-.4c-1.1-1.7-1.6-3.7-1.6-5.8 0-5.9 4.9-10.8 10.9-10.8s10.8 4.8 10.8 10.8S21.9 26.4 16 26.4z"
          ></path>
        </svg>
        <span>Abrir WhatsApp</span>
      </a>
    </div>
  </div>

  <h2 class="text-base md:text-lg font-semibold text-slate-900 mb-3">
    De un mensaje a una visita confirmada y venta en camino (en vivo):
  </h2>

  <div class="grid gap-3 md:grid-cols-3">
    <article class="card border border-base-300 bg-base-100 shadow-sm">
      <div class="card-body p-4">
        <span class="badge badge-neutral w-fit">1</span>
        <h2 class="font-semibold text-slate-900">Iniciás el contacto (WhatsApp)</h2>
        <p class="text-sm text-slate-600">
          Enviás un mensaje con el código del proyecto. El asistente responde, hace preguntas y califica al
          interesado.
        </p>
      </div>
    </article>
    <article class="card border border-base-300 bg-base-100 shadow-sm">
      <div class="card-body p-4">
        <span class="badge badge-neutral w-fit">2</span>
        <h2 class="font-semibold text-slate-900">Ves todo en el Orquestador</h2>
        <p class="text-sm text-slate-600">
          Te llega una URL para abrir el tablero y ver en tiempo real qué mensajes entran, a qué proyecto pertenecen y
          qué queda pendiente.
        </p>
      </div>
    </article>
    <article class="card border border-base-300 bg-base-100 shadow-sm">
      <div class="card-body p-4">
        <span class="badge badge-neutral w-fit">3</span>
        <h2 class="font-semibold text-slate-900">Respondés como vendedor y coordinás visita</h2>
        <p class="text-sm text-slate-600">
          Desde el tablero proponés días y horarios de visita. El cliente elige una opción y queda confirmada, con
          registro y trazabilidad.
        </p>
      </div>
    </article>
  </div>
</section>
