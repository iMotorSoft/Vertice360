const PROJECTS = [
  "OBRA_PALERMO_01",
  "OBRA_NUNEZ_02",
  "OBRA_CABALLITO_03",
  "OBRA_BELGRANO_04",
];

const STATUS_CYCLE = [
  "Pendiente de visita",
  "Esperando confirmación",
  "Nuevo",
  "En seguimiento",
  "Visita confirmada",
];

const MESSAGE_BY_STATUS = {
  "Pendiente de visita": "¿Qué días tienen para visitar esta semana?",
  "Esperando confirmación": "Estoy viendo las opciones, te confirmo hoy.",
  Nuevo: "Hola, me interesa una unidad de 2 ambientes.",
  "En seguimiento": "¿Podés pasarme opciones de financiación?",
  "Visita confirmada": "Perfecto, confirmo la visita. Muchas gracias.",
};

const pad = (value) => String(value).padStart(2, "0");

const buildTimestamp = (day, hour, minute) =>
  `2026-02-${pad(day)}T${pad(hour)}:${pad(minute)}:00-03:00`;

const conversationPhone = (index) => {
  const middle = String(1200 + index).padStart(4, "0");
  const end = String(3200 + index).padStart(4, "0");
  return `+54 9 11 ${middle}-${end}`;
};

const createConversation = (index) => {
  const estado = STATUS_CYCLE[index % STATUS_CYCLE.length];
  const dayBase = 10 + (index % 6);
  const activityHour = 9 + (index % 9);
  const activityMinute = index % 2 === 0 ? 10 : 40;
  const createdAt = buildTimestamp(dayBase - 1, 8 + (index % 6), 15);
  const lastActivityAt = buildTimestamp(dayBase, activityHour, activityMinute);
  const nextVisitProposalAt =
    estado === "Esperando confirmación"
      ? buildTimestamp(dayBase + 1, 18, index % 2 === 0 ? 0 : 30)
      : null;
  const visitAt =
    estado === "Visita confirmada"
      ? buildTimestamp(dayBase + 1, 11 + (index % 3), index % 2 === 0 ? 0 : 30)
      : null;

  return {
    id: `cv-${index + 1}`,
    proyecto: PROJECTS[index % PROJECTS.length],
    cliente: conversationPhone(index + 1),
    estado,
    ultimoMensaje: MESSAGE_BY_STATUS[estado],
    createdAt,
    lastActivityAt,
    visitAt,
    nextVisitProposalAt,
    aiResponded: index % 6 === 0,
  };
};

export const orquestadorAds = [
  {
    id: "ad-1",
    title: "BULNES_966_ALMAGRO",
    line1:
      "Monoambientes y 2 ambientes en Almagro, ideal inversión o primera vivienda.",
    line2: "Solarium + bicicletero para una vida urbana práctica.",
    chips: ["Almagro", "Inversión", "Solarium", "Bicicletero"],
  },
  {
    id: "ad-2",
    title: "GDR_3760_SAAVEDRA",
    line1: "3 ambientes adaptable a 4: viví ‘como en una casa’.",
    line2: "Balcones aterrazados con parrilla y terraza privada en último piso.",
    chips: ["Saavedra", "3→4 amb", "Parrilla", "Terraza privada"],
  },
  {
    id: "ad-3",
    title: "MANZANARES_3277",
    line1: "Espacios inteligentes y confort premium para vivir o invertir.",
    line2: "Seguridad + domótica y detalles de calidad que se notan.",
    chips: ["Domótica", "Seguridad", "Premium", "Alta demanda"],
  },
];

export const orquestadorKpis = [
  { label: "Consultas hoy", value: "38" },
  { label: "Nuevos leads", value: "16" },
  { label: "En seguimiento", value: "21" },
  { label: "Visitas propuestas", value: "13" },
  { label: "Visitas confirmadas", value: "7" },
  { label: "Tiempo respuesta", value: "2m 40s" },
];

export const orquestadorConversations = Array.from({ length: 24 }, (_, index) =>
  createConversation(index),
);
