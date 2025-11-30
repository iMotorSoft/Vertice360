<!-- DEMO – Inventario Pozo360 (NO PRODUCCIÓN) -->
<script lang="ts">
  import { onMount } from "svelte";
  import { API_BASE_URL } from "../../../config/api";

  type Project = {
    id_proyecto: string;
    nombre: string;
    barrio: string;
    ciudad: string;
    fecha_inicio_obra: string;
    fecha_entrega_estimada: string;
    moneda: string;
    precio_desde: number;
    precio_hasta: number;
    estado: string;
  };

  type Unit = {
    id_unidad: string;
    id_proyecto: string;
    piso: number;
    ambiente: string;
    m2_cubiertos: number;
    m2_totales: number;
    precio_lista: number;
    moneda: string;
    estado_unidad: string;
  };

  type Investor = {
    id_inversor: string;
    nombre: string;
    tipo_inversor: string;
    email: string;
    pais: string;
  };

  type Operation = {
    id_operacion: string;
    id_inversor: string;
    id_unidad: string;
    tipo_operacion: string;
    fecha: string;
    monto: number;
    moneda: string;
  };

  let projects = $state<Project[]>([]);
  let selectedProject: Project | null = $state(null);
  let units = $state<Unit[]>([]);
  let investors = $state<Investor[]>([]);
  let operationsByInvestor = $state<Record<string, Operation[]>>({});

  let loadingProjects = $state(true);
  let loadingUnits = $state(false);
  let loadingInvestors = $state(true);
  let error: string | null = $state(null);
  let unitError: string | null = $state(null);
  let investorError: string | null = $state(null);
  let expandedInvestorId: string | null = $state(null);

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
      const res = await fetch(`${API_BASE_URL}/api/demo/codex/projects`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      projects = await res.json();
      if (!selectedProject && projects.length > 0) {
        await selectProject(projects[0]);
      }
    } catch (err) {
      error = err instanceof Error ? err.message : "Error desconocido";
    } finally {
      loadingProjects = false;
    }
  };

  const selectProject = async (project: Project) => {
    selectedProject = project;
    units = [];
    unitError = null;
    loadingUnits = true;
    try {
      const res = await fetch(`${API_BASE_URL}/api/demo/codex/projects/${project.id_proyecto}/units`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      units = await res.json();
    } catch (err) {
      unitError = err instanceof Error ? err.message : "Error desconocido";
    } finally {
      loadingUnits = false;
    }
  };

  const fetchInvestors = async () => {
    loadingInvestors = true;
    investorError = null;
    try {
      const res = await fetch(`${API_BASE_URL}/api/demo/codex/investors`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      investors = await res.json();
    } catch (err) {
      investorError = err instanceof Error ? err.message : "Error desconocido";
    } finally {
      loadingInvestors = false;
    }
  };

  const fetchOperationsForInvestor = async (investorId: string) => {
    if (operationsByInvestor[investorId]) return;
    investorError = null;
    try {
      const res = await fetch(`${API_BASE_URL}/api/demo/codex/investors/${investorId}/operations`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      operationsByInvestor = {
        ...operationsByInvestor,
        [investorId]: await res.json(),
      };
    } catch (err) {
      investorError = err instanceof Error ? err.message : "Error desconocido";
    }
  };

  const toggleInvestor = async (investorId: string) => {
    if (expandedInvestorId === investorId) {
      expandedInvestorId = null;
      return;
    }
    expandedInvestorId = investorId;
    await fetchOperationsForInvestor(investorId);
  };

  const statusChip = (estado: string) => {
    const mapping: Record<string, string> = {
      preventas: "badge-info",
      en_obra: "badge-warning",
      entregado: "badge-success",
      entregada: "badge-success",
      entregados: "badge-success",
    };
    return mapping[estado] ?? "badge-neutral";
  };

  const unitChip = (estado: string) => {
    const mapping: Record<string, string> = {
      disponible: "badge-success",
      reservada: "badge-warning",
      vendida: "badge-neutral",
    };
    return mapping[estado] ?? "badge-outline";
  };

  onMount(() => {
    fetchProjects();
    fetchInvestors();
  });
</script>

<div class="space-y-5">
  <div class="flex items-center justify-between gap-2">
    <div>
      <p class="text-xs uppercase tracking-wide text-emerald-700 font-semibold">Inventario en pozo</p>
      <h2 class="text-xl font-semibold text-emerald-900">Proyectos, unidades y relacionamiento con inversores</h2>
    </div>
  </div>

  <div class="card bg-base-100 shadow">
    <div class="card-body space-y-4">
      <div class="flex items-center justify-between gap-3">
        <h3 class="card-title text-lg">Proyectos en cartera</h3>
        {#if loadingProjects}
          <span class="loading loading-spinner loading-sm" aria-label="Cargando proyectos"></span>
        {/if}
      </div>
      {#if error}
        <div class="alert alert-error text-sm">
          <span>Error cargando proyectos: {error}</span>
        </div>
      {:else}
        <div class="grid gap-3 md:grid-cols-2">
          {#each projects as project (project.id_proyecto)}
            <article
              class={`border rounded-lg p-4 transition hover:border-emerald-300 hover:shadow-sm cursor-pointer ${
                selectedProject?.id_proyecto === project.id_proyecto ? "border-emerald-400 bg-emerald-50/60" : "border-base-200"
              }`}
              on:click={() => selectProject(project)}
            >
              <div class="flex items-start justify-between gap-2">
                <div>
                  <p class="text-xs text-neutral-500">{project.id_proyecto}</p>
                  <h4 class="font-semibold text-emerald-900">{project.nombre}</h4>
                  <p class="text-sm text-neutral-600">
                    {project.barrio} · {project.ciudad}
                  </p>
                </div>
                <div class={`badge ${statusChip(project.estado)} capitalize`}>{project.estado}</div>
              </div>
              <div class="mt-3 text-sm text-neutral-600 space-y-1">
                <p>
                  Desde {formatCurrency(project.precio_desde, project.moneda)} a
                  {formatCurrency(project.precio_hasta, project.moneda)}
                </p>
                <p>Inicio de obra: {project.fecha_inicio_obra}</p>
                <p>Entrega estimada: {project.fecha_entrega_estimada}</p>
              </div>
            </article>
          {/each}
        </div>
      {/if}
    </div>
  </div>

  <div class="grid gap-4 lg:grid-cols-2">
    <div class="card bg-base-100 shadow">
      <div class="card-body space-y-3">
        <div class="flex items-center justify-between gap-2">
          <h3 class="card-title text-lg">Unidades del proyecto</h3>
          {#if loadingUnits}
            <span class="loading loading-spinner loading-sm" aria-label="Cargando unidades"></span>
          {/if}
        </div>
        {#if unitError}
          <div class="alert alert-error text-sm">
            <span>Error cargando unidades: {unitError}</span>
          </div>
        {:else if !selectedProject}
          <p class="text-sm text-neutral-500">Elegí un proyecto para ver sus unidades.</p>
        {:else if units.length === 0}
          <p class="text-sm text-neutral-500">No hay unidades para {selectedProject.nombre}.</p>
        {:else}
          <ul class="space-y-3">
            {#each units as unit (unit.id_unidad)}
              <li class="border border-base-200 rounded-lg p-3">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <p class="text-xs text-neutral-500">{unit.id_unidad}</p>
                    <p class="font-semibold text-emerald-900">
                      Piso {unit.piso} · {unit.ambiente}
                    </p>
                    <p class="text-sm text-neutral-600">
                      {unit.m2_cubiertos} m² cubiertos · {unit.m2_totales} m² totales
                    </p>
                  </div>
                  <span class={`badge ${unitChip(unit.estado_unidad)} capitalize`}>{unit.estado_unidad}</span>
                </div>
                <p class="mt-2 text-sm text-emerald-800">
                  Lista: {formatCurrency(unit.precio_lista, unit.moneda)}
                </p>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>

    <div class="card bg-base-100 shadow">
      <div class="card-body space-y-3">
        <div class="flex items-center justify-between gap-2">
          <h3 class="card-title text-lg">Vista de inversores</h3>
          {#if loadingInvestors}
            <span class="loading loading-spinner loading-sm" aria-label="Cargando inversores"></span>
          {/if}
        </div>
        {#if investorError}
          <div class="alert alert-error text-sm">
            <span>Error cargando inversores: {investorError}</span>
          </div>
        {:else if investors.length === 0}
          <p class="text-sm text-neutral-500">Sin inversores para esta demo.</p>
        {:else}
          <ul class="space-y-3">
            {#each investors as investor (investor.id_inversor)}
              <li class="border border-base-200 rounded-lg p-3 space-y-2">
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <p class="text-xs text-neutral-500">{investor.id_inversor}</p>
                    <p class="font-semibold text-emerald-900">{investor.nombre}</p>
                    <p class="text-sm text-neutral-600">
                      {investor.tipo_inversor} · {investor.pais}
                    </p>
                    <p class="text-xs text-neutral-500">{investor.email}</p>
                  </div>
                  <button class="btn btn-sm btn-ghost" on:click={() => toggleInvestor(investor.id_inversor)}>
                    {expandedInvestorId === investor.id_inversor ? "Ocultar" : "Ver"} operaciones
                  </button>
                </div>

                {#if expandedInvestorId === investor.id_inversor}
                  <div class="border-t border-base-200 pt-2">
                    {#if investorError}
                      <p class="text-xs text-error">Error: {investorError}</p>
                    {:else if !operationsByInvestor[investor.id_inversor]}
                      <span class="loading loading-dots loading-xs"></span>
                    {:else if operationsByInvestor[investor.id_inversor].length === 0}
                      <p class="text-sm text-neutral-500">Sin movimientos registrados.</p>
                    {:else}
                      <ul class="space-y-2">
                        {#each operationsByInvestor[investor.id_inversor] as op (op.id_operacion)}
                          <li class="text-sm text-neutral-700">
                            <div class="flex items-center justify-between gap-2">
                              <span class="font-medium capitalize">{op.tipo_operacion}</span>
                              <span class="text-xs text-neutral-500">{op.fecha}</span>
                            </div>
                            <p class="text-xs text-neutral-600">
                              Unidad {op.id_unidad} · {formatCurrency(op.monto, op.moneda)}
                            </p>
                          </li>
                        {/each}
                      </ul>
                    {/if}
                  </div>
                {/if}
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>
  </div>
</div>
