export interface GatewayEndpointMetrics {
  health_score: number;
  success_count: number;
  failure_count: number;
}

export interface GatewayStatus {
  total_calls: number;
  total_cost_usd: number;
  endpoints: Record<string, GatewayEndpointMetrics>;
}

export interface InferenceCall {
  timestamp: number;
  model_label: string;
  model_actual: string;
  provider: string;
  fallback_used: boolean;
  duration_ms: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  error: string | null;
}

export interface GatewayRecent {
  calls: InferenceCall[];
}
