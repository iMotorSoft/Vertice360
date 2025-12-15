<!-- DEMO – Simulador comercial Vertice360 (NO PRODUCCIÓN) -->
<script lang="ts">
  import { onMount } from "svelte";
  import { URL_REST } from "../../global";

  type Project = {
    id_proyecto: string;
    nombre: string;
    moneda: string;
  };

  type Unit = {
    id_unidad: string;
    id_proyecto: string;
    precio_lista: number;
    moneda: string;
    estado_unidad: string;
  };

  type Investor = {
    id_inversor: string;
    nombre: string;
    tipo_inversor: string;
  };

  type LeadPreview = {
    project?: Project | null;
    unit?: Unit | null;
    investor?: Investor | null;
    reserva_porcentaje: number;
    contacto: string;
    nota: string;
  };

  let projects = $state<Project[]>([]);
  let investors = $state<Investor[]>([]);
  let units = $state<Unit[]>([]);

  let selectedProjectId = $state("");
  let selectedUnitId = $state("");
  let selectedInvestorId = $state("");
  let reservaPorcentaje = $state(15);
  let contacto = $state("llamada");
  let nota = $state("Cliente interesado en tipología con vista abierta.");

  let loadingProjects = $state(true);
  let loadingUnits = $state(false);
  let loadingInvestors = $state(true);
  let error: string | null = $state(null);
  let unitError: string | null = $state(null);

  let preview: LeadPreview = $state({
    reserva_porcentaje: reservaPorcentaje,
    contacto,
    nota,
  });

  const formatCurrency = (value: number, currency: string) =>
    new Intl.NumberFormat("es-AR", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(value);

  const fetchProjects = async () => {
    loadingProjects = true;
    error = null;
    try {
      const res = await fetch(`${URL_REST}/api/demo/codex/projects`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      projects = await res.json();
    } catch (err) {
      error = err instanceof Error ? err.message : "Error desconocido";
    } finally {
      loadingProjects = false;
    }
  };

  const fetchInvestors = async () => {
    loadingInvestors = true;
    error = null;
    try {
      const res = await fetch(`${URL_REST}/api/demo/codex/investors`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      investors = await res.json();
    } catch (err) {
      error = err instanceof Error ? err.message : "Error desconocido";
    } finally {
      loadingInvestors = false;
    }
  };

  const fetchUnitsForProject = async (projectId: string) => {
    if (!projectId) {
      units = [];
      return;
    }
    loadingUnits = true;
    unitError = null;
    try {
      const res = await fetch(`${URL_REST}/api/demo/codex/projects/${projectId}/units`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      units = await res.json();
    } catch (err) {
      unitError = err instanceof Error ? err.message : "Error desconocido";
    } finally {
      loadingUnits = false;
    }
  };

  const refreshPreview = () => {
    preview = {
      project: projects.find((p) => p.id_proyecto === selectedProjectId),
      unit: units.find((u) => u.id_unidad === selectedUnitId),
      investor: investors.find((i) => i.id_inversor === selectedInvestorId),
      reserva_porcentaje: reservaPorcentaje,
      contacto,
      nota,
    };
  };

  const handleProjectChange = async (projectId: string) => {
    selectedProjectId = projectId;
    selectedUnitId = "";
    await fetchUnitsForProject(projectId);
    refreshPreview();
  };

  const handleUnitChange = (unitId: string) => {
    selectedUnitId = unitId;
    refreshPreview();
  };

  const handleInvestorChange = (investorId: string) => {
    selectedInvestorId = investorId;
    refreshPreview();
  };

  onMount(() => {
    fetchProjects();
    fetchInvestors();
  });

  $effect(() => {
    refreshPreview();
  });
</script>

<div class="card bg-gradient-to-br from-emerald-900 via-emerald-800 to-emerald-700 text-emerald-50 shadow-lg">
  <div class="card-body space-y-4">
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="text-xs uppercase tracking-wide text-emerald-200">Lead-to-Reserva (mock)</p>
        <h3 class="card-title text-2xl text-white">Simulador comercial</h3>
        <p class="text-sm text-emerald-100">
          Arma un caso ficticio combinando inversor, proyecto y unidad para ver cómo fluye una reserva.
        </p>
      </div>
    </div>

    {#if error}
      <div class="alert alert-error bg-opacity-20 border-0 text-sm">
        <span>Error cargando datos: {error}</span>
      </div>
    {/if}

    <div class="space-y-3">
      <label class="form-control w-full">
        <div class="label">
          <span class="label-text text-emerald-50">Inversor</span>
        </div>
        <select
          class="select select-bordered select-sm bg-emerald-800 border-emerald-600 text-emerald-50"
          bind:value={selectedInvestorId}
          on:change={(ev) => handleInvestorChange((ev.target as HTMLSelectElement).value)}
        >
          <option value="">Elegir inversor</option>
          {#each investors as investor}
            <option value={investor.id_inversor}>
              {investor.nombre} · {investor.tipo_inversor}
            </option>
          {/each}
        </select>
      </label>

      <label class="form-control w-full">
        <div class="label">
          <span class="label-text text-emerald-50">Proyecto en pozo</span>
          {#if loadingProjects}
            <span class="loading loading-dots loading-xs"></span>
          {/if}
        </div>
        <select
          class="select select-bordered select-sm bg-emerald-800 border-emerald-600 text-emerald-50"
          bind:value={selectedProjectId}
          on:change={(ev) => handleProjectChange((ev.target as HTMLSelectElement).value)}
        >
          <option value="">Elegir proyecto</option>
          {#each projects as project}
            <option value={project.id_proyecto}>{project.nombre}</option>
          {/each}
        </select>
      </label>

      <label class="form-control w-full">
        <div class="label">
          <span class="label-text text-emerald-50">Unidad</span>
          {#if loadingUnits}
            <span class="loading loading-dots loading-xs"></span>
          {/if}
        </div>
        <select
          class="select select-bordered select-sm bg-emerald-800 border-emerald-600 text-emerald-50"
          bind:value={selectedUnitId}
          on:change={(ev) => handleUnitChange((ev.target as HTMLSelectElement).value)}
          disabled={!selectedProjectId}
        >
          <option value="">{selectedProjectId ? "Elegir unidad" : "Seleccioná un proyecto"}</option>
          {#if unitError}
            <option disabled>Error: {unitError}</option>
          {/if}
          {#each units as unit}
            <option value={unit.id_unidad} disabled={unit.estado_unidad !== "disponible"}>
              {unit.id_unidad} · {unit.estado_unidad}
            </option>
          {/each}
        </select>
        {#if selectedUnitId === "" && selectedProjectId}
          <span class="text-xs text-emerald-200 mt-1">Filtramos por proyecto para mostrar solo sus unidades disponibles.</span>
        {/if}
      </label>

      <div class="grid grid-cols-2 gap-3">
        <label class="form-control">
          <div class="label">
            <span class="label-text text-emerald-50">% de reserva</span>
          </div>
          <input
            type="range"
            min="5"
            max="30"
            step="1"
            class="range range-sm range-success"
            bind:value={reservaPorcentaje}
            on:input={refreshPreview}
          />
          <div class="text-xs text-emerald-100 mt-1">{reservaPorcentaje}% del precio lista</div>
        </label>

        <label class="form-control">
          <div class="label">
            <span class="label-text text-emerald-50">Contacto</span>
          </div>
          <select
            class="select select-bordered select-sm bg-emerald-800 border-emerald-600 text-emerald-50"
            bind:value={contacto}
            on:change={refreshPreview}
          >
            <option value="llamada">Llamada</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="mail">Email</option>
          </select>
        </label>
      </div>

      <label class="form-control">
        <div class="label">
          <span class="label-text text-emerald-50">Nota interna</span>
        </div>
        <textarea
          class="textarea textarea-bordered bg-emerald-800 border-emerald-600 text-emerald-50"
          rows="2"
          bind:value={nota}
          on:input={refreshPreview}
        ></textarea>
      </label>
    </div>

    <div class="rounded-lg bg-emerald-950/40 border border-emerald-700 p-4 space-y-3">
      <p class="text-sm uppercase tracking-wide text-emerald-200 font-semibold">Resumen mock</p>
      {#if !preview.project || !preview.unit || !preview.investor}
        <p class="text-emerald-100 text-sm">
          Seleccioná inversor, proyecto y unidad para armar una propuesta de reserva ficticia.
        </p>
      {:else}
        <div class="space-y-2 text-emerald-50 text-sm">
          <p>
            <span class="font-semibold">Inversor:</span> {preview.investor.nombre} ({preview.investor.tipo_inversor})
          </p>
          <p>
            <span class="font-semibold">Proyecto:</span> {preview.project.nombre}
          </p>
          <p>
            <span class="font-semibold">Unidad:</span> {preview.unit.id_unidad} · {preview.unit.estado_unidad}
          </p>
          <p>
            <span class="font-semibold">Seña estimada:</span>
            {formatCurrency((preview.unit.precio_lista * preview.reserva_porcentaje) / 100, preview.unit.moneda)}
            ({preview.reserva_porcentaje}%)
          </p>
          <p>
            <span class="font-semibold">Canal:</span> {preview.contacto}
          </p>
          <p class="text-emerald-100">
            <span class="font-semibold">Nota:</span> {preview.nota}
          </p>
        </div>
      {/if}
    </div>
  </div>
</div>
