export interface AtlasList<T> { data: T[]; }
export interface ExtractionRun {
  id: string; source_document_id: string; source_report_type: string;
  status: string; payload: any; updated_at: string;
}
export interface ExtractionBatchRequest {
  published_from: string | null;
  published_to: string | null;
  report_types: string[] | null;
  limit: number;
  force: boolean;
}
export interface ExtractionBatchResponse {
  count: number;
  runs: any[];
}
export interface GovernanceRecord {
  id: string; kind: string; version: string; status: string;
  payload: any; created_at: string;
}
export type ProposalStatus = 'PROPOSED' | 'ACCEPTED' | 'REJECTED';
export interface ReportTypeAssessment {
  report_type: string;
  sampled_document_count: number;
  readable_document_count: number;
  useful_document_count: number;
  useful_ratio: number;
  enabled_for_production: boolean;
  prompt_profile_key: string | null;
  rationale: string;
}
export interface SemanticProposal {
  proposal_id: string;
  canonical_name: string;
  display_name: string;
  description: string;
  occurrence_count: number;
  status: ProposalStatus;
  concept_type?: string;
  subject_types?: string[];
  object_types?: string[];
}
export interface DiscoveryPayload {
  run_id: string;
  status: string;
  requested_sample_size: number;
  sampled_document_ids: string[];
  report_type_assessments: ReportTypeAssessment[];
  predicate_proposals: SemanticProposal[];
  concept_proposals: SemanticProposal[];
  document_results: unknown[];
}
export interface KnowledgeEntity {
  id: string; canonical_name: string; normalized_name: string; entity_type: string;
  country_code: string; resolution_state: string; attributes: Record<string, unknown>;
}
export interface GraphStats { entities: number; claims: number; }
