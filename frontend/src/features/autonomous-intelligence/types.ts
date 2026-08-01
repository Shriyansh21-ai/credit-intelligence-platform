// Phase 9 — Autonomous AI Banking Intelligence types (kept intentionally light;
// the backend returns rich dicts and the UI reads defensively).

export interface GraphNode {
  id: number;
  ref: string;
  name: string;
  entity_type: string;
  risk_score: number | null;
  propagated_risk?: number | null;
  depth?: number;
}
export interface GraphEdge {
  id: number;
  source: number;
  target: number;
  rel_type: string;
  strength: number;
  exposure: number | null;
}
export interface Network {
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_count: number;
  edge_count: number;
}

export interface Signal {
  id: number;
  source: string;
  signal_type: string;
  severity: string;
  direction: string;
  detail: string | null;
  priority_score: number;
  detected_at: string | null;
}

export interface Alert {
  id: number;
  company_ref: string;
  category: string;
  alert_type: string;
  title: string;
  severity: string;
  confidence: number;
  priority_score: number;
  business_impact: string | null;
  recommended_action: string | null;
  status: string;
}

export interface EWSResult {
  company_ref: string;
  ews_score: number;
  ews_band: string;
  signal_count: number;
  signals: Array<Record<string, unknown>>;
  summary: string;
}

export interface CopilotAnswer {
  conversation_id: number;
  message_id: number;
  intent: string;
  provider: string;
  answer: string;
  grounding: Record<string, unknown>;
  citations: Array<Record<string, unknown>>;
}

export interface Recommendation {
  id?: number;
  action: string;
  title: string;
  reason: string;
  confidence: number;
  priority: string;
  evidence: Array<Record<string, unknown>>;
  supporting_metrics: Record<string, unknown>;
  status?: string;
}

export type Json = Record<string, unknown>;
