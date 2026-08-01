/** Shared loose types for the AI Intelligence Platform feature (Track 2). */

export interface RagHit {
  chunk_id?: number;
  document_id?: number;
  source_type?: string;
  title?: string;
  ordinal?: number;
  snippet?: string;
  score?: number;
}

export interface Citation {
  index: number;
  label: string;
  snippet?: string;
  score?: number;
}

export interface AgentContribution {
  role: string;
  title: string;
  summary: string;
  signal: string;
  confidence: number;
  recommendation: string;
}

export type Json = Record<string, any>;
