import assert from "node:assert/strict";
import { test } from "node:test";
import { AmlApiError, createAmlClient } from "./aml-client.mjs";
import { createViteAmlClient } from "./vite-client.js";

const bases = {
  alertsBaseUrl: "http://localhost:8001",
  graphBaseUrl: "http://localhost:8002",
  explanationBaseUrl: "http://localhost:8003",
  analysisBaseUrl: "http://localhost:8004",
};
const jsonResponse = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

test("Vite adapter maps four explicit env variables without a common-URL fallback", () => {
  const client = createViteAmlClient({
    VITE_ALERTS_BASE_URL: bases.alertsBaseUrl,
    VITE_GRAPH_BASE_URL: bases.graphBaseUrl,
    VITE_EXPLANATION_BASE_URL: bases.explanationBaseUrl,
    VITE_ANALYSIS_BASE_URL: bases.analysisBaseUrl,
  });
  assert.deepEqual(client.baseUrls, bases);
  assert.throws(() => createViteAmlClient({ VITE_API_BASE_URL: "http://localhost:8000" }), /alertsBaseUrl/);
});

test("all six operations select their owning service, preserve payloads and timezone queries", async () => {
  const calls = [];
  const client = createAmlClient(bases, async (url, options) => {
    calls.push({ url: new URL(url), ...options });
    return jsonResponse({ ok: true }, options.method === "POST" ? 202 : 200);
  });
  const start = "2022-11-01T09:00:00+09:00";
  await client.listAlerts({ start, end: "2022-11-02T09:00:00+09:00", page: 2, pageSize: 5, minScore: 0 });
  await client.getAlert("TX000003");
  await client.getGraph("TX000003", { hops: 3, lookbackDays: 10 });
  await client.requestExplanation("TX000003", { modelVersion: "fraudgt-mock-v1" });
  await client.getExplanation("TX000003", { modelVersion: "fraudgt-mock-v1" });
  await client.getAnalysis("TX000003");
  assert.deepEqual(calls.map(({ url }) => url.origin), [
    bases.alertsBaseUrl, bases.alertsBaseUrl, bases.graphBaseUrl,
    bases.explanationBaseUrl, bases.explanationBaseUrl, bases.analysisBaseUrl,
  ]);
  assert.deepEqual(calls.map(({ method }) => method), ["GET", "GET", "GET", "POST", "GET", "GET"]);
  assert.deepEqual(calls.map(({ url }) => url.pathname), [
    "/api/alerts", "/api/alerts/TX000003", "/api/alerts/TX000003/graph",
    "/api/alerts/TX000003/explanation", "/api/alerts/TX000003/explanation", "/api/alerts/TX000003/analysis",
  ]);
  assert.equal(calls[0].url.searchParams.get("start"), start);
  assert.equal(calls[0].url.searchParams.get("page_size"), "5");
  assert.equal(calls[0].url.searchParams.get("min_score"), "0");
  assert.equal(calls[2].url.searchParams.get("lookback_days"), "10");
  assert.deepEqual(JSON.parse(calls[3].body), { model_version: "fraudgt-mock-v1" });
  assert.equal(calls[3].headers["Content-Type"], "application/json");
  assert.equal(calls[4].url.searchParams.get("model_version"), "fraudgt-mock-v1");
});

test("real service URL migration changes config alone and supports proxy prefixes/trailing slashes", async () => {
  const calls = [];
  const migrated = { ...bases, graphBaseUrl: "https://models.example.test/graph-service///" };
  const client = createAmlClient(migrated, async (url) => {
    calls.push(url);
    return jsonResponse({ transaction_id: "TX000003" });
  });
  await client.getGraph("TX000003");
  assert.equal(calls[0], "https://models.example.test/graph-service/api/alerts/TX000003/graph");
  assert.ok(Object.isFrozen(client.baseUrls));
});

test("missing or malformed service URLs fail before any request", () => {
  for (const key of Object.keys(bases)) {
    assert.throws(() => createAmlClient({ ...bases, [key]: undefined }), new RegExp(key));
  }
  for (const value of ["/relative", "ftp://host", "https://user:pass@host", "https://host?q=1", "https://host/#hash", "http://host/api/", "https://host/proxy/api"]) {
    assert.throws(() => createAmlClient({ ...bases, graphBaseUrl: value }), /graphBaseUrl/);
  }
});

test("unsafe transaction IDs cannot alter endpoint routing", () => {
  const client = createAmlClient(bases, () => assert.fail("unexpected network request"));
  for (const id of ["", "..", "../analysis", "TX/3", "TX?other=1", "TX 3", 3]) {
    assert.throws(() => client.getGraph(id), /transactionId/);
  }
});

test("HTTP error status and machine code retain their service", async () => {
  const client = createAmlClient(bases, async () => jsonResponse({
    error: { code: "ALERT_NOT_FOUND", message: "Unknown transaction", details: [] },
  }, 404));
  await assert.rejects(client.getAnalysis("TX999999"), (error) => {
    assert.ok(error instanceof AmlApiError);
    assert.equal(error.status, 404);
    assert.equal(error.code, "ALERT_NOT_FOUND");
    assert.equal(error.service, "analysis");
    assert.equal(error.message, "Unknown transaction");
    return true;
  });
});

test("non-JSON HTTP errors remain useful and successful invalid JSON is rejected", async () => {
  const failed = createAmlClient(bases, async () => new Response("proxy unavailable", { status: 503 }));
  await assert.rejects(failed.getAlert("TX000003"), (error) => error.status === 503 && error.code === "HTTP_ERROR");
  const invalid = createAmlClient(bases, async () => new Response("not JSON", { status: 200 }));
  await assert.rejects(invalid.getGraph("TX000003"), /Invalid JSON from graph/);
});

test("polling accepts pending then completed without assuming immediate Mock completion", async () => {
  let polls = 0;
  const client = createAmlClient(bases, async (url) => {
    assert.equal(new URL(url).origin, bases.explanationBaseUrl);
    return jsonResponse({ status: ++polls < 3 ? "pending" : "completed", edge_importance: [] });
  });
  const result = await client.waitForExplanation("TX000003", { pollIntervalMs: 1, timeoutMs: 1000 });
  assert.equal(result.status, "completed");
  assert.equal(polls, 3);
});

test("a failed explanation is a returned job state while not_requested is explicit", async () => {
  const failed = createAmlClient(bases, async () => jsonResponse({ status: "failed", error: { code: "MOCK_FAILURE" } }));
  assert.equal((await failed.waitForExplanation("TX000018")).status, "failed");
  const absent = createAmlClient(bases, async () => jsonResponse({ status: "not_requested" }));
  await assert.rejects(absent.waitForExplanation("TX000003"), /call requestExplanation first/);
});

test("polling timeout aborts an in-flight fetch rather than only checking between requests", async () => {
  let aborted = false;
  const client = createAmlClient(bases, (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => { aborted = true; reject(signal.reason); }, { once: true });
  }));
  await assert.rejects(client.waitForExplanation("TX000003", { timeoutMs: 15 }), /polling timed out/);
  assert.ok(aborted);
});

test("component cancellation stops polling and does not start a pre-aborted request", async () => {
  const controller = new AbortController();
  const reason = new Error("component unmounted");
  let calls = 0;
  const client = createAmlClient(bases, async () => {
    calls++;
    controller.abort(reason);
    return jsonResponse({ status: "pending" });
  });
  await assert.rejects(client.waitForExplanation("TX000003", { signal: controller.signal }), /component unmounted/);
  assert.equal(calls, 1);
  await assert.rejects(client.getAlert("TX000003", { signal: controller.signal }), /component unmounted/);
  assert.equal(calls, 1);
});

test("polling bounds must be finite positive numbers", async () => {
  const client = createAmlClient(bases, () => assert.fail("unexpected request"));
  for (const options of [{ timeoutMs: 0 }, { timeoutMs: Infinity }, { pollIntervalMs: -1 }]) {
    await assert.rejects(client.waitForExplanation("TX000003", options), /positive finite/);
  }
});
