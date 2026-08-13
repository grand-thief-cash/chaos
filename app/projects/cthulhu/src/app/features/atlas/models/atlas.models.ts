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

export interface SampleRun {
  id: string;
  status: string;
  cronjob_run_id: number | null;
  current: number;
  total: number;
  progress_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
  request_payload: Record<string, unknown>;
}
export interface SampleCategoryResult {
  id: string;
  sample_run_id: string;
  report_type: string;
  document_count: number;
  raw_results: Array<{
    document_id: string;
    title: string;
    s3_path: string;
    report_type: string;
    extraction_run_id: string;
    extraction_result: unknown | null;
    // Free-form per-PDF extraction (discovery phase). Present when the sample
    // run used the two-stage free-extraction path; absent for legacy strict runs.
    free_extraction_result?: unknown | null;
    discovery_result: unknown;
  }>;
  field_summary: {
    report_type?: string;
    recommended_fields?: Array<{
      field_name: string;
      description: string;
      rationale: string;
      occurrence_count: number;
    }>;
    recommended_prompt_profile_key?: string | null;
    notes?: string;
  } | null;
  generated_at: string | null;
}
export interface SampleRunRequest {
  sample_size: number;
  report_types: string[];
  published_from: string | null;
  published_to: string | null;
  force: boolean;
}
