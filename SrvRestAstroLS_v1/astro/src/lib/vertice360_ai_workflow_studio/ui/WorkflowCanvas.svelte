<script>
  const nodes = [
    {
      id: "normalize_input",
      label: "Normalize input",
      detail: "clean + normalize",
    },
    {
      id: "intent_classify",
      label: "Intent classify",
      detail: "multi-intent scoring",
    },
    {
      id: "extract_entities",
      label: "Extract entities",
      detail: "email / phone / dni",
    },
    { id: "pragmatics", label: "Pragmatics", detail: "speech act + slots" },
    { id: "decide_next", label: "Decide next", detail: "routing logic" },
    {
      id: "build_response",
      label: "Build response",
      detail: "deterministic reply",
    },
  ];

  let { activeNodeId = null, activeRunId = null, stepsByNodeId = {} } = $props();

  const isActive = (nodeId) => nodeId && nodeId === activeNodeId;

  const getStep = (nodeId) => stepsByNodeId?.[nodeId] || null;

  const statusLabel = (nodeId) => {
    if (isActive(nodeId)) return "running";
    const step = getStep(nodeId);
    if (!step?.status) return "idle";
    if (step.status === "failed") return "failed";
    if (step.status === "completed") return "completed";
    return step.status;
  };

  const statusTone = (label) => {
    if (label === "running") return "badge-info";
    if (label === "completed") return "badge-success";
    if (label === "failed") return "badge-error";
    return "badge-ghost";
  };

  const durationMs = (nodeId) => {
    const step = getStep(nodeId);
    if (!step?.endedAt || !step?.startedAt) return null;
    const duration = step.endedAt - step.startedAt;
    if (!Number.isFinite(duration) || duration < 0) return null;
    if (statusLabel(nodeId) !== "completed") return null;
    return Math.round(duration);
  };

  const compactData = (value) => {
    if (!value || typeof value !== "object") return "";
    try {
      const text = JSON.stringify(value);
      if (text.length > 200) {
        return `${text.slice(0, 197)}...`;
      }
      return text;
    } catch (err) {
      return "";
    }
  };

  const tooltipText = (nodeId) => {
    const step = getStep(nodeId);
    if (!step) return "No step data yet.";
    const summary = step.summary || "No summary.";
    const data = compactData(step.data);
    if (!data) return summary;
    return `${summary}\n${data}`;
  };
</script>

<div
  class="card overflow-hidden border border-base-200 bg-base-100/90 shadow-sm"
>
  <div class="card-body gap-4 p-5">
    <div class="flex items-center justify-between gap-4 min-w-0">
      <div>
        <p
          class="text-xs uppercase tracking-[0.3em] text-slate-500 font-semibold"
        >
          Workflow map
        </p>
        <h3 class="text-lg font-semibold text-slate-900">
          Deterministic pipeline
        </h3>
      </div>
      <div class="badge badge-outline text-xs">
        Active run {activeRunId || "--"}
      </div>
    </div>

    <div class="space-y-3">
      {#each nodes as node, index}
        {@const label = statusLabel(node.id)}
        {@const duration = durationMs(node.id)}
        <div
          class={`flex items-center gap-3 min-w-0 rounded-2xl border px-4 py-3 transition ${
            isActive(node.id)
              ? "border-primary/40 bg-primary/10"
              : "border-base-200 bg-white"
          }`}
          title={tooltipText(node.id)}
        >
          <div
            class={`flex h-9 w-9 items-center justify-center min-w-0 rounded-full text-xs font-semibold ${
              isActive(node.id)
                ? "bg-primary text-primary-content"
                : "bg-base-200 text-base-content"
            }`}
          >
            {index + 1}
          </div>
          <div class="min-w-0">
            <p class="font-semibold text-sm text-slate-900 truncate">
              {node.label}
            </p>
            <p class="text-xs text-neutral-500 truncate">{node.detail}</p>
          </div>
          <div class="ml-auto flex flex-wrap items-center justify-end gap-2 min-w-0">
            {#if duration !== null}
              <span class="badge badge-outline badge-sm text-xs">{duration}ms</span>
            {/if}
            <span class={`badge badge-sm ${statusTone(label)}`}>{label}</span>
          </div>
        </div>
      {/each}
    </div>
  </div>
</div>
