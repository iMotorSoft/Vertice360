/**
 * Shared SSE management with automatic reconnection and exponential backoff.
 * Derived from vertice360_workflow/sse.js.
 */

const backoffDelay = (attempt) => {
    const base = 500;
    const delay = base * Math.pow(2, attempt);
    return Math.min(delay, 5000);
};

export const parseEvent = (event) => {
    if (!event?.data) return null;
    try {
        const payload = JSON.parse(event.data);
        if (!payload || payload.type !== "CUSTOM") return null;
        return {
            name: payload.name,
            timestamp: payload.timestamp ?? payload.ts ?? Date.now(),
            correlationId: payload.correlationId ?? payload.ticketId ?? payload?.value?.ticketId,
            value: payload.value ?? {},
            raw: payload,
        };
    } catch (err) {
        return null;
    }
};

/**
 * Creates and manages an EventSource connection.
 */
export function createSseManager(url, { eventTypes = [], onStatus, onEvent } = {}) {
    let source = null;
    let reconnectTimer = null;
    let reconnectAttempt = 0;
    let isUnloading = false;

    const handle = (event) => {
        const parsed = parseEvent(event);
        if (parsed) onEvent?.(parsed);
    };

    const disconnect = () => {
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
        if (source) {
            source.close();
            source = null;
        }
    };

    const connect = () => {
        if (typeof window === "undefined") return;
        if (isUnloading) return;

        if (source && (source.readyState === EventSource.OPEN || source.readyState === EventSource.CONNECTING)) {
            return;
        }

        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }

        try {
            source = new EventSource(url);

            eventTypes.forEach((evt) => source.addEventListener(evt, handle));

            source.onopen = () => {
                reconnectAttempt = 0;
                onStatus?.(true);
            };

            source.onerror = () => {
                if (isUnloading) return;
                onStatus?.(false);
                if (source) {
                    source.close();
                    source = null;
                }
                if (reconnectTimer) return;
                const delay = backoffDelay(reconnectAttempt);
                reconnectTimer = setTimeout(() => {
                    reconnectTimer = null;
                    reconnectAttempt += 1;
                    connect();
                }, delay);
            };
        } catch (err) {
            onStatus?.(false);
        }
    };

    if (typeof window !== "undefined") {
        window.addEventListener("beforeunload", () => {
            isUnloading = true;
            disconnect();
        });
    }

    return {
        connect,
        disconnect,
        get isConnected() {
            return source?.readyState === EventSource.OPEN;
        },
    };
}
