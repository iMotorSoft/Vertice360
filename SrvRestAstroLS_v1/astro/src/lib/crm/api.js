import { URL_REST } from "../../components/global";

const jsonHeaders = { "Content-Type": "application/json" };

const request = async (path, options = {}) => {
  const res = await fetch(`${URL_REST}${path}`, {
    ...options,
    headers: { ...jsonHeaders, ...(options.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
};

export const fetchConversations = () => request("/api/demo/crm/inbox/conversations");
export const fetchConversation = (id) => request(`/api/demo/crm/inbox/conversations/${id}`);
export const sendMessage = (id, text) =>
  request(`/api/demo/crm/inbox/conversations/${id}/send`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
export const simulateInbound = ({ channel, conversationId, text }) =>
  request("/api/demo/crm/mock/inbound", {
    method: "POST",
    body: JSON.stringify({ channel, conversationId, text }),
  });

export const fetchPipeline = () => request("/api/demo/crm/pipeline");
export const moveDeal = (id, toStageId) =>
  request(`/api/demo/crm/deals/${id}/move`, {
    method: "POST",
    body: JSON.stringify({ toStageId }),
  });

export const fetchTasks = () => request("/api/demo/crm/tasks");
export const createTask = ({ title, leadId, dealId, dueAt }) =>
  request("/api/demo/crm/tasks", {
    method: "POST",
    body: JSON.stringify({ title, leadId, dealId, dueAt }),
  });
export const completeTask = (id) => request(`/api/demo/crm/tasks/${id}/complete`, { method: "POST" });

