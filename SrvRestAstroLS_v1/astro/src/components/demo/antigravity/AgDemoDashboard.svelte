<!-- DEMO – Componente generado con Antigravity (AG-UI) para Pozo360 (NO PRODUCCIÓN) -->
<script>
  import { onMount } from 'svelte';

  let projects = [];
  let selectedProject = null;
  let units = [];
  let loading = true;
  let loadingUnits = false;

  onMount(async () => {
    try {
      const res = await fetch('/api/demo/ag/projects');
      if (res.ok) {
        projects = await res.json();
        if (projects.length > 0) {
          selectProject(projects[0]);
        }
      }
    } catch (e) {
      console.error("Error fetching projects", e);
    } finally {
      loading = false;
    }
  });

  async function selectProject(project) {
    selectedProject = project;
    loadingUnits = true;
    units = [];
    try {
      const res = await fetch(`/api/demo/ag/projects/${project.id_proyecto}/units`);
      if (res.ok) {
        units = await res.json();
      }
    } catch (e) {
      console.error("Error fetching units", e);
    } finally {
      loadingUnits = false;
    }
  }

  $: totalUnits = units.length;
  $: availableUnits = units.filter(u => u.estado_unidad === 'disponible').length;
  $: soldUnits = units.filter(u => u.estado_unidad === 'vendida' || u.estado_unidad === 'reservada').length;
</script>

<div class="space-y-6">
  <div class="card bg-base-100 shadow-xl">
    <div class="card-body">
      <h2 class="card-title text-primary">Proyectos en Pozo</h2>
      <p class="text-sm text-neutral-500">Selecciona un proyecto para ver sus unidades.</p>
      
      {#if loading}
        <div class="flex justify-center p-4">
          <span class="loading loading-spinner loading-lg"></span>
        </div>
      {:else}
        <div class="overflow-x-auto">
          <table class="table table-zebra w-full">
            <thead>
              <tr>
                <th>ID</th>
                <th>Nombre</th>
                <th>Ubicación</th>
                <th>Estado</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {#each projects as p}
                <tr class:active={selectedProject?.id_proyecto === p.id_proyecto}>
                  <td class="font-mono text-xs">{p.id_proyecto}</td>
                  <td class="font-bold">{p.nombre}</td>
                  <td>{p.barrio}, {p.ciudad}</td>
                  <td>
                    <div class="badge badge-outline capitalize">{p.estado.replace('_', ' ')}</div>
                  </td>
                  <td>
                    <button 
                      class="btn btn-sm btn-ghost"
                      class:btn-active={selectedProject?.id_proyecto === p.id_proyecto}
                      on:click={() => selectProject(p)}
                    >
                      Ver Unidades
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  </div>

  {#if selectedProject}
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div class="stats shadow">
        <div class="stat">
          <div class="stat-title">Total Unidades</div>
          <div class="stat-value text-primary">{totalUnits}</div>
          <div class="stat-desc">En {selectedProject.nombre}</div>
        </div>
      </div>
      
      <div class="stats shadow">
        <div class="stat">
          <div class="stat-title">Disponibles</div>
          <div class="stat-value text-success">{availableUnits}</div>
          <div class="stat-desc">Para venta inmediata</div>
        </div>
      </div>
      
      <div class="stats shadow">
        <div class="stat">
          <div class="stat-title">Vendidas / Reservadas</div>
          <div class="stat-value text-secondary">{soldUnits}</div>
          <div class="stat-desc">Ocupación actual</div>
        </div>
      </div>
    </div>

    <div class="card bg-base-100 shadow-xl">
      <div class="card-body">
        <h3 class="card-title">
          Unidades: <span class="text-primary">{selectedProject.nombre}</span>
        </h3>
        
        {#if loadingUnits}
          <div class="flex justify-center p-8">
            <span class="loading loading-dots loading-lg"></span>
          </div>
        {:else if units.length === 0}
          <div class="alert alert-info">
            <span>No hay unidades registradas para este proyecto en la demo.</span>
          </div>
        {:else}
          <div class="overflow-x-auto max-h-96">
            <table class="table table-pin-rows">
              <thead>
                <tr>
                  <th>Unidad</th>
                  <th>Piso</th>
                  <th>Ambientes</th>
                  <th>M2 Totales</th>
                  <th>Precio ({selectedProject.moneda})</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {#each units as u}
                  <tr>
                    <td class="font-bold">{u.id_unidad}</td>
                    <td>{u.piso}</td>
                    <td>{u.ambiente}</td>
                    <td>{u.m2_totales} m²</td>
                    <td class="font-mono">${u.precio_lista.toLocaleString()}</td>
                    <td>
                      {#if u.estado_unidad === 'disponible'}
                        <div class="badge badge-success gap-2">Disponible</div>
                      {:else if u.estado_unidad === 'reservada'}
                        <div class="badge badge-warning gap-2">Reservada</div>
                      {:else}
                        <div class="badge badge-error gap-2">Vendida</div>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>
