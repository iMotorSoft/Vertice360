<script>
  import { URL_SVG_XMLNS, URL_WA_ME } from "../../global.js";

  const demoPhoneHuman = "+4526325250";
  const demoPhoneWa = "4526325250";
  const waText = "OBRA_PALERMO_01";
  const waUrl = `${URL_WA_ME}/${demoPhoneWa}/?text=${encodeURIComponent(waText)}`;
</script>

<section class="mx-auto max-w-3xl grid grid-cols-1 md:grid-cols-2">
  <div class="space-y-2 md:my-6 md:mr-3 mx-3 md:mx-0">
    <p
      class="text-xs uppercase tracking-[0.25em] text-emerald-700 font-semibold"
    >
      Vertice360 Demo
    </p>
    <h1 class="text-2xl md:text-3xl">Vertice360 Orquestador</h1>
    <p class="text-sm md:text-lg text-slate-600">
      Orquestá tus leads por WhatsApp, automatizá el seguimiento y tené control
      total: del anuncio al cierre.
    </p>
  </div>

  <div class="card-primary md:ml-5 my-6">
    <div class="card-body gap-4 md:px-8">
      <p class="text-sm md:text-lg text-slate-700">
        Para iniciar la demo, enviá un WhatsApp a:
      </p>
      <p class="text-md md:text-xl font-semibold tracking-wide text-slate-600">
        {demoPhoneHuman}
      </p>
      <a
        href={waUrl}
        target="_blank"
        rel="noreferrer"
        class="btn-primary font-semibold text-sm h-10 md:h-12 inline-flex items-center justify-center
        gap-2 md:gap-3"
      >
        <svg
          xmlns={URL_SVG_XMLNS}
          viewBox="0 0 24 24"
          class="h-4 w-4 md:h-5 md:w-5 fill-current"
          aria-hidden="true"
        >
          <path
            d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"
          />
        </svg>
        <span>Abrir WhatsApp</span>
      </a>
    </div>
  </div>

  <h2
    class="text-sm md:text-xl font-semibold text-slate-900 md:mb-3 col-span-1
    md:col-span-2 mx-3 md:mx-0 mt-3"
  >
    De un mensaje a una visita confirmada y venta en camino (en vivo):
  </h2>

  <div
    class="grid gap-3 md:grid-cols-3 col-span-1 md:col-span-2 my-6 text-sm md:text-base"
  >
    <div class="card-primary p-4 md:space-y-2 grid grid-cols-5 md:grid-cols-1">
      <div
        class="border-2 border-emerald-700 text-emerald-900
        font-semibold rounded-full w-8 h-8 flex items-center justify-center
        col-span-1 md:col-span-1"
      >
        1
      </div>
      <h2
        class="font-semibold text-emerald-900 col-span-4 md:col-span-1 flex items-center md:items-start"
      >
        Iniciás el contacto (WhatsApp)
      </h2>
      <p class="text-slate-600 col-span-5 md:col-span-1 mt-3 md:mt-0">
        Enviás un mensaje con el código del proyecto. El asistente responde,
        hace preguntas y califica al interesado.
      </p>
    </div>
    <div class="card-primary p-4 md:space-y-2 grid grid-cols-5 md:grid-cols-1">
      <div
        class="border-2 border-emerald-700 text-emerald-900
        font-semibold rounded-full w-8 h-8 flex items-center justify-center
        col-span-1 md:col-span-1"
      >
        2
      </div>
      <h2
        class="font-semibold text-emerald-900 col-span-4 md:col-span-1 flex items-center md:items-start"
      >
        Ves todo en el Orquestador
      </h2>
      <p class="text-slate-600 col-span-5 md:col-span-1 mt-3 md:mt-0">
        Te llega una URL para abrir el tablero y ver en tiempo real qué mensajes
        entran, a qué proyecto pertenecen y qué queda pendiente.
      </p>
    </div>
    <div class="card-primary p-4 md:space-y-2 grid grid-cols-5 md:grid-cols-1">
      <div
        class="border-2 border-emerald-700 text-emerald-900
        font-semibold rounded-full w-8 h-8 flex items-center justify-center
        col-span-1 md:col-span-1"
      >
        3
      </div>
      <h2
        class="font-semibold text-emerald-900 col-span-4 md:col-span-1 flex items-center md:items-start"
      >
        Respondés como vendedor y coordinás visita
      </h2>
      <p class="text-slate-600 col-span-5 md:col-span-1 mt-3 md:mt-0">
        Desde el tablero proponés días y horarios de visita. El cliente elige
        una opción y queda confirmada, con registro y trazabilidad.
      </p>
    </div>
  </div>
</section>
