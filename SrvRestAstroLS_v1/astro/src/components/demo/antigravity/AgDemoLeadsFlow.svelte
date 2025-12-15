<!-- DEMO – Componente generado con Antigravity (AG-UI) para Vertice360 (NO PRODUCCIÓN) -->
<script>
  import { onMount } from 'svelte';

  let investors = [];
  let selectedInvestor = null;
  let operations = [];
  let loading = true;
  let loadingOps = false;

  // Formulario simple de demo
  let newLeadName = "";
  let newLeadEmail = "";
  let showSuccessAlert = false;

  onMount(async () => {
    try {
      const res = await fetch('/api/demo/ag/investors');
      if (res.ok) {
        investors = await res.json();
      }
    } catch (e) {
      console.error("Error fetching investors", e);
    } finally {
      loading = false;
    }
  });

  async function selectInvestor(investor) {
    selectedInvestor = investor;
    loadingOps = true;
    operations = [];
    try {
      const res = await fetch(`/api/demo/ag/investors/${investor.id_inversor}/operations`);
      if (res.ok) {
        operations = await res.json();
      }
    } catch (e) {
      console.error("Error fetching operations", e);
    } finally {
      loadingOps = false;
    }
  }

  function handleDemoSubmit() {
    if (!newLeadName || !newLeadEmail) return;
    // Simulación de envío
    showSuccessAlert = true;
    setTimeout(() => {
      showSuccessAlert = false;
      newLeadName = "";
      newLeadEmail = "";
    }, 3000);
  }
</script>

<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
  <!-- Columna Izquierda: Lista de Inversores -->
  <div class="lg:col-span-2 space-y-6">
    <div class="card bg-base-100 shadow-xl">
      <div class="card-body">
        <h2 class="card-title text-secondary">Cartera de Inversores</h2>
        <p class="text-sm text-neutral-500">Gestión de clientes y sus operaciones.</p>

        {#if loading}
          <div class="flex justify-center p-4">
            <span class="loading loading-spinner loading-md"></span>
          </div>
        {:else}
          <div class="overflow-x-auto">
            <table class="table table-zebra w-full">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Tipo</th>
                  <th>Email</th>
                  <th>País</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {#each investors as inv}
                  <tr class:active={selectedInvestor?.id_inversor === inv.id_inversor}>
                    <td class="font-bold">{inv.nombre}</td>
                    <td>
                      {#if inv.tipo_inversor === 'institucional'}
                        <div class="badge badge-primary badge-outline">Institucional</div>
                      {:else}
                        <div class="badge badge-ghost badge-outline">Minorista</div>
                      {/if}
                    </td>
                    <td class="text-xs">{inv.email}</td>
                    <td>{inv.pais}</td>
                    <td>
                      <button 
                        class="btn btn-xs btn-secondary btn-outline"
                        on:click={() => selectInvestor(inv)}
                      >
                        Ver Ops
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

    {#if selectedInvestor}
      <div class="card bg-base-100 shadow-xl border-l-4 border-secondary">
        <div class="card-body">
          <h3 class="card-title text-base">
            Operaciones de: <span class="font-bold">{selectedInvestor.nombre}</span>
          </h3>

          {#if loadingOps}
            <div class="flex justify-center p-4">
              <span class="loading loading-dots loading-md"></span>
            </div>
          {:else if operations.length === 0}
            <div class="alert alert-warning text-sm">
              <span>Este inversor no tiene operaciones registradas en la demo.</span>
            </div>
          {:else}
            <table class="table table-sm">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Tipo</th>
                  <th>Unidad</th>
                  <th>Monto</th>
                </tr>
              </thead>
              <tbody>
                {#each operations as op}
                  <tr>
                    <td class="font-mono text-xs">{op.fecha}</td>
                    <td class="capitalize font-semibold">{op.tipo_operacion}</td>
                    <td>{op.id_unidad}</td>
                    <td class="font-mono text-right">${op.monto.toLocaleString()} {op.moneda}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </div>
      </div>
    {/if}
  </div>

  <!-- Columna Derecha: Formulario Demo -->
  <div class="lg:col-span-1">
    <div class="card bg-base-200 shadow-lg sticky top-4">
      <div class="card-body">
        <h2 class="card-title text-accent">Nuevo Lead (Demo)</h2>
        <p class="text-xs mb-4">Simula la carga de un interesado.</p>

        <div class="form-control w-full">
          <label class="label">
            <span class="label-text">Nombre Completo</span>
          </label>
          <input 
            type="text" 
            placeholder="Ej: Juan Pérez" 
            class="input input-bordered w-full" 
            bind:value={newLeadName}
          />
        </div>

        <div class="form-control w-full mt-2">
          <label class="label">
            <span class="label-text">Email</span>
          </label>
          <input 
            type="email" 
            placeholder="juan@example.com" 
            class="input input-bordered w-full" 
            bind:value={newLeadEmail}
          />
        </div>

        <div class="form-control w-full mt-2">
          <label class="label">
            <span class="label-text">Interés Principal</span>
          </label>
          <select class="select select-bordered">
            <option disabled selected>Seleccionar...</option>
            <option>Inversión en Vertice</option>
            <option>Compra Final</option>
            <option>Alquiler</option>
          </select>
        </div>

        <div class="card-actions justify-end mt-6">
          <button class="btn btn-accent w-full" on:click={handleDemoSubmit}>
            Registrar Lead
          </button>
        </div>

        {#if showSuccessAlert}
          <div class="toast toast-end">
            <div class="alert alert-success text-white text-sm">
              <span>Lead registrado (Simulación)</span>
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>
