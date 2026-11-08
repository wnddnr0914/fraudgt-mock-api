/** Dependency-free browser/Node client for the four independently deployed AML services. */

const SERVICE_KEYS = ["alertsBaseUrl", "graphBaseUrl", "explanationBaseUrl", "analysisBaseUrl"];

function normalizeBaseUrl(value, name) {
  if (typeof value !== "string" || !value.trim()) {
    throw new TypeError(`${name} is required; configure each service Base URL explicitly`);
  }
  let url;
  try {
    url = new URL(value.trim());
  } catch {
    throw new TypeError(`${name} must be an absolute HTTP(S) URL`);
  }
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new TypeError(`${name} must be an HTTP(S) origin or path prefix without credentials, query or fragment`);
  }
  url.pathname = url.pathname.replace(/\/+$/, "");
  if (url.pathname.endsWith("/api")) {
    throw new TypeError(`${name} must exclude /api; the client appends the API paths`);
  }
  return url.toString().replace(/\/+$/, "");
}

function transactionPath(transactionId) {
  if (typeof transactionId !== "string" || !/^[A-Za-z0-9_-]{1,160}$/.test(transactionId)) {
    throw new TypeError("transactionId must contain 1..160 letters, digits, underscores or hyphens");
  }
  return `/api/alerts/${encodeURIComponent(transactionId)}`;
}

function modelQuery(modelVersion) {
  if (modelVersion === undefined) return {};
  if (typeof modelVersion !== "string" || !modelVersion.trim()) {
    throw new TypeError("modelVersion must be a nonempty string when provided");
  }
  return { model_version: modelVersion };
}

function aborted(signal) {
  if (signal?.aborted) throw signal.reason ?? new DOMException("Request aborted", "AbortError");
}

function delay(milliseconds, signal) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(signal.reason ?? new DOMException("Request aborted", "AbortError"));
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(signal.reason ?? new DOMException("Request aborted", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, milliseconds);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

export class AmlApiError extends Error {
  constructor(service, url, status, body) {
    super(body?.error?.message ?? `HTTP ${status} from ${service} service`);
    this.name = "AmlApiError";
    this.service = service;
    this.url = url;
    this.status = status;
    this.code = body?.error?.code ?? "HTTP_ERROR";
    this.details = body?.error?.details ?? [];
    this.body = body;
  }
}

/**
 * Base URLs are service origins (optionally with a reverse-proxy prefix), WITHOUT /api.
 * All four values are required. Changing service addresses never requires changing the methods below.
 */
export function createAmlClient(config, fetchImpl = globalThis.fetch) {
  if (typeof fetchImpl !== "function") throw new TypeError("A fetch implementation is required");
  const baseUrls = Object.freeze(Object.fromEntries(
    SERVICE_KEYS.map((key) => [key, normalizeBaseUrl(config?.[key], key)]),
  ));

  async function request(service, path, { query = {}, body, signal, method = "GET" } = {}) {
    aborted(signal);
    const url = new URL(`${baseUrls[`${service}BaseUrl`]}${path}`);
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    }
    const headers = { Accept: "application/json" };
    const options = { method, headers, signal, credentials: "omit" };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetchImpl(url.toString(), options);
    let data;
    try {
      data = await response.json();
    } catch {
      if (!response.ok) throw new AmlApiError(service, url.toString(), response.status, null);
      throw new Error(`Invalid JSON from ${service} service`);
    }
    if (!response.ok) throw new AmlApiError(service, url.toString(), response.status, data);
    return data;
  }

  const client = {
    baseUrls,
    listAlerts({ start, end, page, pageSize, minScore }, { signal } = {}) {
      if (typeof start !== "string" || !start || typeof end !== "string" || !end) {
        throw new TypeError("start and end must be timezone-aware ISO 8601 strings");
      }
      return request("alerts", "/api/alerts", {
        query: { start, end, page, page_size: pageSize, min_score: minScore }, signal,
      });
    },
    getAlert(transactionId, { signal } = {}) {
      return request("alerts", transactionPath(transactionId), { signal });
    },
    getGraph(transactionId, { hops, lookbackDays } = {}, { signal } = {}) {
      return request("graph", `${transactionPath(transactionId)}/graph`, {
        query: { hops, lookback_days: lookbackDays }, signal,
      });
    },
    requestExplanation(transactionId, { modelVersion } = {}, { signal } = {}) {
      return request("explanation", `${transactionPath(transactionId)}/explanation`, {
        method: "POST", body: modelQuery(modelVersion), signal,
      });
    },
    getExplanation(transactionId, { modelVersion } = {}, { signal } = {}) {
      return request("explanation", `${transactionPath(transactionId)}/explanation`, {
        query: modelQuery(modelVersion), signal,
      });
    },
    getAnalysis(transactionId, { signal } = {}) {
      return request("analysis", `${transactionPath(transactionId)}/analysis`, { signal });
    },
    async waitForExplanation(transactionId, {
      modelVersion, pollIntervalMs = 500, timeoutMs = 60_000, signal,
    } = {}) {
      if (!Number.isFinite(pollIntervalMs) || pollIntervalMs <= 0 ||
          !Number.isFinite(timeoutMs) || timeoutMs <= 0) {
        throw new TypeError("pollIntervalMs and timeoutMs must be positive finite numbers");
      }
      aborted(signal);
      const controller = new AbortController();
      const onAbort = () => controller.abort(signal.reason);
      signal?.addEventListener("abort", onAbort, { once: true });
      const timeout = setTimeout(() => controller.abort(
        new Error(`Explanation polling timed out after ${timeoutMs} ms`),
      ), timeoutMs);
      try {
        while (true) {
          aborted(controller.signal);
          const result = await client.getExplanation(transactionId, { modelVersion }, { signal: controller.signal });
          if (result.status === "completed" || result.status === "failed") return result;
          if (result.status === "not_requested") {
            throw new Error("Explanation has not been requested; call requestExplanation first");
          }
          if (result.status !== "pending") throw new Error(`Unknown explanation status: ${result.status}`);
          await delay(pollIntervalMs, controller.signal);
        }
      } finally {
        clearTimeout(timeout);
        signal?.removeEventListener("abort", onAbort);
      }
    },
  };
  return Object.freeze(client);
}
