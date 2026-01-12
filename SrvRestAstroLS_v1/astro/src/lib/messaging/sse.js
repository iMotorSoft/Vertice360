export const parseSseData = (raw) => {
  if (raw === undefined || raw === null) {
    return { kind: "empty", raw: "" };
  }

  if (typeof raw !== "string") {
    return { kind: "unknown", raw };
  }

  try {
    const parsed = JSON.parse(raw);
    if (parsed && parsed.type === "CUSTOM") {
      return {
        kind: "custom",
        name: typeof parsed.name === "string" ? parsed.name : "CUSTOM",
        timestamp: parsed.timestamp ?? parsed.ts ?? null,
        value: parsed.value ?? null,
        raw: parsed,
      };
    }

    return { kind: "json", value: parsed, raw: parsed };
  } catch (err) {
    return { kind: "text", value: raw, raw };
  }
};

export const connectSSE = (url, handlers = {}) => {
  const source = new EventSource(url);
  const events = Array.isArray(handlers.events) ? handlers.events : [];
  const onEvent = typeof handlers.onEvent === "function" ? handlers.onEvent : null;

  events.forEach((evt) => {
    source.addEventListener(evt, (event) => onEvent?.(event));
  });

  source.onmessage = (event) => onEvent?.(event);

  if (typeof handlers.onOpen === "function") {
    source.onopen = handlers.onOpen;
  }

  if (typeof handlers.onError === "function") {
    source.onerror = handlers.onError;
  }

  return source;
};
