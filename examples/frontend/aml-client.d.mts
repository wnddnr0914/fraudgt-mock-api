export interface ServiceBaseUrls {
  alertsBaseUrl: string;
  graphBaseUrl: string;
  explanationBaseUrl: string;
  analysisBaseUrl: string;
}
export interface RequestOptions { signal?: AbortSignal }
export interface Alert {
  transaction_id: string; timestamp: string; sender_account: string; receiver_account: string;
  amount: number; currency: string; fraud_score: number; is_alert: boolean; model_version: string;
  predicted_typology: string | null; typology_confidence: number | null;
  typology_model_version: string | null; status: "unreviewed";
}
export interface AlertList { total: number; page: number; page_size: number; alerts: Alert[] }
export interface GraphEdge {
  id: string; source: string; target: string; amount: number; currency: string;
  timestamp: string; is_target: boolean;
}
export interface GraphResponse {
  transaction_id: string;
  graph: {
    hops: number; lookback_days: number; neighborhood_direction: "both";
    window_start: string; window_end: string; nodes: { id: string }[]; edges: GraphEdge[];
  };
}
export interface GraphSnapshot {
  graph_id: string; transaction_id: string; model_version: string; preprocessing_version: string;
  sampler: string; seed: number; hops: number; lookback_days: number;
  edge_transaction_ids: string[]; node_account_ids: string[];
}
export interface ErrorInfo { code: string; message: string; details: Record<string, unknown>[] }
export interface ExplanationAccepted {
  transaction_id: string; explanation_id: string; status: "pending" | "completed" | "failed";
  model_version: string;
}
export interface Explanation {
  transaction_id: string; explanation_id: string | null;
  status: "not_requested" | "pending" | "completed" | "failed";
  method: "GNNExplainer"; model_version: string; graph_snapshot: GraphSnapshot | null;
  edge_importance: { transaction_id: string; importance: number }[]; error: ErrorInfo | null;
}
export interface Analysis {
  transaction_id: string; fraud_score: number; model_version: string;
  typology: {
    predicted_type: string; confidence: number;
    verification_status: "unverified" | "verified" | "rejected"; model_version: string;
  } | null;
  evidence: {
    related_transaction_ids: string[]; account_path: string[]; description: string;
  } | null;
}
export interface ModelQuery { modelVersion?: string }
export interface AmlClient {
  readonly baseUrls: Readonly<ServiceBaseUrls>;
  listAlerts(query: { start: string; end: string; page?: number; pageSize?: number; minScore?: number }, options?: RequestOptions): Promise<AlertList>;
  getAlert(transactionId: string, options?: RequestOptions): Promise<Alert>;
  getGraph(transactionId: string, query?: { hops?: number; lookbackDays?: number }, options?: RequestOptions): Promise<GraphResponse>;
  requestExplanation(transactionId: string, query?: ModelQuery, options?: RequestOptions): Promise<ExplanationAccepted>;
  getExplanation(transactionId: string, query?: ModelQuery, options?: RequestOptions): Promise<Explanation>;
  getAnalysis(transactionId: string, options?: RequestOptions): Promise<Analysis>;
  waitForExplanation(transactionId: string, options?: ModelQuery & RequestOptions & { pollIntervalMs?: number; timeoutMs?: number }): Promise<Explanation & { status: "completed" | "failed" }>;
}
export class AmlApiError extends Error {
  service: string; url: string; status: number; code: string;
  details: Record<string, unknown>[]; body: unknown;
}
export function createAmlClient(config: ServiceBaseUrls, fetchImpl?: typeof fetch): AmlClient;
