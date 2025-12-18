<script lang="ts">
  export let title = "Sin datos";
  export let description = "Todavía no hay información para mostrar.";
  export let icon = "icon-[heroicons-face-smile-20-solid]";
</script>

<div class="text-center space-y-2 text-slate-600">
  <div class="flex justify-center">
    <div class="rounded-full bg-base-200 text-base-content/70 p-3">
      <span class={icon}></span>
    </div>
  </div>
  <h4 class="text-lg font-semibold text-slate-900">{title}</h4>
  <p class="text-sm text-slate-500">{description}</p>
</div>

