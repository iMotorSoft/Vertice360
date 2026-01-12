import { URL_REST } from "../../components/global";

const API_BASE = `${URL_REST}/api/demo/vertice360-workflow`;

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

export const listTickets = () => requestJson("/tickets");
export const getTicket = (ticketId) => requestJson(`/tickets/${ticketId}`);
export const assignTicket = (ticketId, payload) => postJson(`/tickets/${ticketId}/assign`, payload);
export const updateStatus = (ticketId, payload) => postJson(`/tickets/${ticketId}/status`, payload);
export const docsAction = (ticketId, payload) => postJson(`/tickets/${ticketId}/docs`, payload);
export const closeTicket = (ticketId, payload) => postJson(`/tickets/${ticketId}/close`, payload);
export const escalateTicket = (ticketId, payload) => postJson(`/tickets/${ticketId}/escalate`, payload);
export const simulateBreach = (ticketId, payload) => postJson(`/tickets/${ticketId}/simulate-breach`, payload);
export const resetDemo = () => postJson("/reset", {});
