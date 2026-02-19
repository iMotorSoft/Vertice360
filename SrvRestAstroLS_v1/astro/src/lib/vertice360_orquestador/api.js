import { getRestBaseUrl } from "../../components/global.js";

const API_PREFIX = "/api/demo/vertice360-orquestador/";
const DEFAULT_TIMEOUT_MS = 12000;

export const getBaseUrl = () => getRestBaseUrl();

const buildRequestUrl = (path) => {
  const apiBase = new URL(API_PREFIX, `${getBaseUrl()}/`);
  const relative = String(path || "").replace(/^\/+/, "");
  return new URL(relative, apiBase).toString();
};

const buildQueryString = (params = {}) => {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value === undefined || value === null) continue;
    const clean = String(value).trim();
    if (!clean) continue;
    query.set(key, clean);
  }
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
};

const mergeSignals = (externalSignal, timeoutMs) => {
  if (!timeoutMs || timeoutMs <= 0) {
    return { signal: externalSignal ?? undefined, cleanup: () => {} };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(new Error("request-timeout")), timeoutMs);

  const onAbort = () => {
    controller.abort(externalSignal?.reason);
  };

  if (externalSignal) {
    if (externalSignal.aborted) {
      onAbort();
    } else {
      externalSignal.addEventListener("abort", onAbort, { once: true });
    }
  }

  return {
    signal: controller.signal,
    cleanup: () => {
      clearTimeout(timeoutId);
      if (externalSignal) {
        externalSignal.removeEventListener("abort", onAbort);
      }
    },
  };
};

const parseErrorPayload = async (response) => {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string" && data.detail.trim()) {
      return data.detail;
    }
    if (typeof data?.message === "string" && data.message.trim()) {
      return data.message;
    }
    if (typeof data?.error === "string" && data.error.trim()) {
      return data.error;
    }
    return JSON.stringify(data);
  } catch {
    try {
      const text = await response.text();
      return text || `HTTP ${response.status}`;
    } catch {
      return `HTTP ${response.status}`;
    }
  }
};

const request = async (path, { method = "GET", body, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) => {
  const url = buildRequestUrl(path);
  const { signal: mergedSignal, cleanup } = mergeSignals(signal, timeoutMs);

  try {
    const response = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: mergedSignal,
    });

    if (!response.ok) {
      const detail = await parseErrorPayload(response);
      throw new Error(detail || `HTTP ${response.status}`);
    }

    if (response.status === 204) {
      return {};
    }

    return await response.json();
  } catch (err) {
    if (err?.name === "AbortError") {
      throw new Error("La solicitud excedió el tiempo de espera.");
    }
    throw err;
  } finally {
    cleanup();
  }
};

export const bootstrap = async ({ cliente, signal } = {}) => {
  const query = buildQueryString({ cliente });
  return request(`bootstrap${query}`, { method: "GET", signal });
};

export const dashboard = async ({ cliente, signal } = {}) => {
  const query = buildQueryString({ cliente });
  return request(`dashboard${query}`, { method: "GET", signal });
};

export const ticketDetail = async ({ ticketId, signal } = {}) => {
  if (!ticketId) throw new Error("ticketId es requerido");
  return request(`ticket/${encodeURIComponent(ticketId)}`, { method: "GET", signal });
};

export const ingestMessage = async (payload, { signal } = {}) => {
  return request("ingest_message", { method: "POST", body: payload, signal });
};

export const proposeVisit = async (payload, { signal } = {}) => {
  return request("visit/propose", { method: "POST", body: payload, signal });
};

export const confirmVisit = async (payload, { signal } = {}) => {
  return request("visit/confirm", { method: "POST", body: payload, signal });
};

export const rescheduleVisit = async (payload, { signal } = {}) => {
  return request("visit/reschedule", { method: "POST", body: payload, signal });
};

export const supervisorSend = async (payload, { signal } = {}) => {
  return request("supervisor/send", { method: "POST", body: payload, signal });
};
