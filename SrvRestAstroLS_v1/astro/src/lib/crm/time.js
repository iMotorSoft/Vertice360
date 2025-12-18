const rtf = new Intl.RelativeTimeFormat("es", { numeric: "auto" });

const dividers = [
  { amount: 60, name: "second" },
  { amount: 60, name: "minute" },
  { amount: 24, name: "hour" },
  { amount: 7, name: "day" },
  { amount: 4.34524, name: "week" },
  { amount: 12, name: "month" },
  { amount: Number.POSITIVE_INFINITY, name: "year" },
];

export const relativeTime = (input) => {
  const date = typeof input === "number" ? new Date(input) : new Date(input ?? Date.now());
  const elapsed = (date.getTime() - Date.now()) / 1000;
  let duration = elapsed;
  let unit = "second";
  for (const divider of dividers) {
    if (Math.abs(duration) < divider.amount) {
      return rtf.format(Math.round(duration), unit);
    }
    duration /= divider.amount;
    unit = divider.name;
  }
  return rtf.format(Math.round(duration), unit);
};

export const formatDateTime = (input) =>
  new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(typeof input === "number" ? new Date(input) : new Date(input ?? Date.now()));

