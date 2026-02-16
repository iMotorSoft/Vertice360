import { URL_REST } from "../../components/global.js";

const API_BASE = `${URL_REST}/api/demo/vertice360-ai-workflow`;
const MESSAGING_API_BASE = `${URL_REST}/api/demo/messaging`;
const WORKFLOW_OPERATOR_API_BASE = `${URL_REST}/api/demo/workflow/operator`;

const readError = async (response) => {
  try {
    const payload = await response.json();
    if (payload?.detail) return payload.detail;
    if (payload?.error) return payload.error;
    return JSON.stringify(payload);
  } catch (err) {
    return response.statusText || "Request failed";
  }
};

const requestJson = async (path, options = {}) => {
  const url = `${API_BASE}${path}`;
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      const error = await readError(response);
      return { ok: false, error };
    }
    const data = await response.json();
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Network error" };
  }
};

const postJson = (path, body) =>
  requestJson(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body ?? {}),
  });

const normalizeProvider = (value) => {
  const raw = (value || "").toString().trim().toLowerCase();
  if (raw === "gupshup" || raw === "gupshup_whatsapp" || raw === "gs") {
    return "gupshup";
  }
  return "meta";
};

export const startRun = ({ input, workflowId = "vertice360-ai-workflow", mode = "heuristic" } = {}) =>
  postJson("/runs", {
    workflowId,
    input,
    mode,
  });

export const listRuns = () => requestJson("/runs");

const readSendError = async (response, fallbackProvider) => {
  let payload = null;
  try {
    payload = await response.json();
  } catch (err) {
    payload = null;
  }

  const provider =
    payload?.provider ||
    fallbackProvider ||
    "meta";
  const upstreamStatus =
    payload?.error?.upstream_status ??
    payload?.error?.status_code ??
    payload?.status_code ??
    null;
  const message =
    payload?.error?.message ||
    payload?.detail ||
    (typeof payload?.error === "string" ? payload.error : "") ||
    response.statusText ||
    "Request failed";

  return {
    provider,
    upstreamStatus:
      typeof upstreamStatus === "number" ? upstreamStatus : null,
    error: message,
    payload,
  };
};

export const sendReply = async ({ ticketId, to, text, provider = "meta" } = {}) => {
  const normalizedProvider = normalizeProvider(provider);
  const body = { provider: normalizedProvider, to, text, ticketId };
  try {
    const response = await fetch(`${MESSAGING_API_BASE}/whatsapp/send`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const error = await readSendError(response, normalizedProvider);
      return {
        ok: false,
        provider: error.provider || normalizedProvider,
        upstreamStatus: error.upstreamStatus,
        error: error.error,
        payload: error.payload,
      };
    }
    const data = await response.json();
    return { ok: true, data };
  } catch (err) {
    return {
      ok: false,
      provider: normalizedProvider,
      upstreamStatus: null,
      error: err instanceof Error ? err.message : "Network error",
      payload: null,
    };
  }
};

export const sendOperatorWhatsApp = async ({
  provider = "meta",
  to,
  text,
  operatorName,
  ticketId,
} = {}) => {
  const normalizedProvider = normalizeProvider(provider);
  const body = {
    provider: normalizedProvider,
    to,
    text,
    operator_name: operatorName,
    ticket_id: ticketId,
  };
  try {
    const response = await fetch(`${WORKFLOW_OPERATOR_API_BASE}/send_whatsapp`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const error = await readSendError(response, normalizedProvider);
      return {
        ok: false,
        provider: error.provider || normalizedProvider,
        upstreamStatus: error.upstreamStatus,
        error: error.error,
        payload: error.payload,
      };
    }
    const data = await response.json();
    return { ok: true, data };
  } catch (err) {
    return {
      ok: false,
      provider: normalizedProvider,
      upstreamStatus: null,
      error: err instanceof Error ? err.message : "Network error",
      payload: null,
    };
  }
};
