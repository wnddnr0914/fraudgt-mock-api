import { createAmlClient } from "./aml-client.mjs";

/** Vite replaces import.meta.env at build time. Restart its dev server after editing .env. */
export function createViteAmlClient(env = import.meta.env) {
  return createAmlClient({
    alertsBaseUrl: env?.VITE_ALERTS_BASE_URL,
    graphBaseUrl: env?.VITE_GRAPH_BASE_URL,
    explanationBaseUrl: env?.VITE_EXPLANATION_BASE_URL,
    analysisBaseUrl: env?.VITE_ANALYSIS_BASE_URL,
  });
}
