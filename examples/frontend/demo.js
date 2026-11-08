import { createViteAmlClient } from "./vite-client.js";

const aml = createViteAmlClient();

/** Example dashboard flow; pass a component-owned AbortController.signal on unmount. */
export async function loadInvestigation(transactionId = "TX000003", signal) {
  const alerts = await aml.listAlerts({
    start: "2022-11-01T00:00:00Z",
    end: "2022-11-02T00:00:00Z",
  }, { signal });

  const [detail, graph, analysis] = await Promise.all([
    aml.getAlert(transactionId, { signal }),
    aml.getGraph(transactionId, { hops: 2, lookbackDays: 7 }, { signal }),
    aml.getAnalysis(transactionId, { signal }),
  ]);

  await aml.requestExplanation(transactionId, { modelVersion: detail.model_version }, { signal });
  const explanation = await aml.waitForExplanation(transactionId, {
    modelVersion: detail.model_version,
    pollIntervalMs: 500,
    timeoutMs: 60_000,
    signal,
  });

  if (explanation.status === "failed") {
    // A job failure is a normal HTTP 200 result, separate from an HTTP/network error.
    return { alerts, detail, graph, analysis, explanation, explanationFailed: true };
  }
  const importanceById = new Map(explanation.edge_importance.map(
    (edge) => [edge.transaction_id, edge.importance],
  ));
  const displayEdges = graph.graph.edges.map((edge) => ({
    ...edge,
    // A narrower display graph may omit edges from the fixed explanation snapshot.
    explanationImportance: importanceById.get(edge.id) ?? null,
  }));
  return { alerts, detail, graph, analysis, explanation, displayEdges, explanationFailed: false };
}
