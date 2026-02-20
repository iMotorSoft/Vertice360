/**
 * Shared HTTP client wrapper with support for AbortController, timeouts, and standard error handling.
 */

const DEFAULT_TIMEOUT_MS = 12000;

const mergeSignals = (externalSignal, timeoutMs) => {
    if (!timeoutMs || timeoutMs <= 0) {
        return { signal: externalSignal ?? undefined, cleanup: () => { } };
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

/**
 * Robust fetch wrapper.
 * @returns {Promise<any>} Response JSON data.
 * @throws {Error} If response is not OK or timeout/abort occurs.
 */
export const request = async (url, { method = "GET", body, signal, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) => {
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
        if (err?.name === "AbortError" || err?.message === "request-timeout") {
            throw new Error("La solicitud excedió el tiempo de espera.");
        }
        throw err;
    } finally {
        cleanup();
    }
};

/**
 * Legacy-style wrapper compatible with newer codebases but returning {ok, data, error}
 */
export const requestJson = async (url, options = {}) => {
    try {
        const data = await request(url, options);
        return { ok: true, data };
    } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : "Network error" };
    }
};
