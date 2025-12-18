<script lang="ts">
  export let toasts: { id: string; message: string; tone?: string }[] = [];

  const toneClass = (tone?: string) => {
    if (tone === "success") return "alert-success";
    if (tone === "error") return "alert-error";
    if (tone === "warning") return "alert-warning";
    return "alert-info";
  };
</script>

<div class="toast toast-end toast-bottom z-50">
  {#each toasts as toast (toast.id)}
    <div class={`alert ${toneClass(toast.tone)} shadow`}>
      <span>{toast.message}</span>
    </div>
  {/each}
</div>

