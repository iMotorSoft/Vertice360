export const STATUS_LABELS = {
  OPEN: "Open",
  IN_PROGRESS: "In progress",
  WAITING_DOCS: "Waiting docs",
  ESCALATED: "Escalated",
  CLOSED: "Closed",
};

export const STATUS_TONES = {
  OPEN: "badge-info",
  IN_PROGRESS: "badge-primary",
  WAITING_DOCS: "badge-warning",
  ESCALATED: "badge-error",
  CLOSED: "badge-ghost",
};

export const CHANNEL_LABELS = {
  whatsapp: "WhatsApp",
  sms: "SMS",
  email: "Email",
};

export const EVENT_GROUPS = [
  { id: "all", label: "Todos" },
  { id: "ticket", label: "ticket.*" },
  { id: "messaging", label: "messaging.*" },
  { id: "workflow", label: "workflow.*" },
];

export const DEFAULT_REQUESTED_DOCS = ["DNI frente", "DNI dorso", "Comprobante de pago", "Formulario reserva"];

export const isTicketEvent = (name) => typeof name === "string" && name.startsWith("ticket.");
export const isMessagingEvent = (name) => typeof name === "string" && name.startsWith("messaging.");
export const isWorkflowEvent = (name) => typeof name === "string" && name.startsWith("workflow.");

export const statusLabel = (status) => STATUS_LABELS[status] || status || "Unknown";
export const statusTone = (status) => STATUS_TONES[status] || "badge-ghost";

export const channelLabel = (channel) => {
  if (!channel) return "";
  const key = String(channel).toLowerCase();
  return CHANNEL_LABELS[key] || key.toUpperCase();
};

export const eventGroup = (name) => {
  if (isTicketEvent(name)) return "ticket";
  if (isMessagingEvent(name)) return "messaging";
  if (isWorkflowEvent(name)) return "workflow";
  return "other";
};
