export type JsonObject = Record<string, unknown>;

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface FeatureDefinition {
  id: number;
  feature_code: string;
  display_name: string;
  description: string;
  kind: string;
  entity_type: string;
  value_type: string;
  unit: string;
  category: string;
  owner: string;
  status: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface FeatureVersion {
  id: number;
  feature_id: number;
  version_number: number;
  status: string;
  frequency: string;
  as_of_semantics: string;
  missing_policy: string;
  manifest_checksum: string;
  manifest_snapshot: JsonObject;
  published_at?: string;
  deprecated_at?: string;
  created_at: string;
  updated_at: string;
}

export interface FeatureImplementation {
  id: number;
  feature_version_id: number;
  kind: string;
  producer_service: string;
  backend: string;
  entrypoint: string;
  implementation_revision: number;
  config: JsonObject;
  checksum: string;
  is_canonical: boolean;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface FeatureDependency {
  id: number;
  feature_version_id: number;
  dependency_kind: 'feature' | 'data_field';
  depends_on_feature_version_id?: number;
  data_field_dictionary_id?: number;
  dependency_ref_snapshot: JsonObject;
  ordinal: number;
  created_at: string;
}

export interface FeatureVersionSummary {
  version: FeatureVersion;
  implementations: FeatureImplementation[];
  dependencies: FeatureDependency[];
}

export interface FeatureDefinitionDetail {
  definition: FeatureDefinition;
  versions: FeatureVersionSummary[];
}

export interface FeatureLineageReference {
  feature_version_id: number;
  feature_code: string;
  version_number: number;
  status: string;
}

export interface FeatureLineageDataField {
  data_field_dictionary_id: number;
  source: string;
  dataset: string;
  data_type: string;
  raw_field: string;
  contract_version: string;
  storage_location: string;
  deprecated: boolean;
}

export interface FeatureLineageVersion {
  feature_version_id: number;
  version_number: number;
  upstream: FeatureDependency[];
  downstream: FeatureDependency[];
  upstream_features: FeatureLineageReference[];
  downstream_features: FeatureLineageReference[];
  upstream_data_fields: FeatureLineageDataField[];
}

export interface FeatureLineage {
  feature_code: string;
  versions: FeatureLineageVersion[];
}

export interface FeatureDataFieldAvailability extends FeatureLineageDataField {
  status: 'ready' | 'missing' | 'unknown';
  sample_count: number;
  last_seen_at?: string;
}

export interface FeatureAvailability {
  feature_code: string;
  source_profile: string;
  latest_published_version_id?: number;
  latest_succeeded_run?: FeatureRun;
  status: string;
  definition_status: string;
  version_status: string;
  dependency_status: string;
  data_status: string;
  implementation_status: string;
  materialization_status: string;
  execution_readiness: string;
  reasons: string[];
  data_fields: FeatureDataFieldAvailability[];
}

export type FeatureRunRequestPayload = JsonObject & {
  root_feature_version_ids?: number[];
  parameters?: JsonObject;
};

export interface FeatureRun {
  run_id: string;
  request_fingerprint: string;
  producer_service: string;
  producer_run_ref: string;
  trigger_type: string;
  as_of_time: string;
  data_cutoff_time: string;
  source_profile: string;
  market: string;
  universe_hash: string;
  request_payload: FeatureRunRequestPayload;
  code_revision: string;
  status: string;
  retry_of_run_id?: string;
  worker_id: string;
  heartbeat_at?: string;
  backfill_id?: string;
  backfill_sequence?: number;
  backfill_attempt?: number;
  started_at?: string;
  finished_at?: string;
  error_code: string;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export interface FeatureRunItem {
  run_id: string;
  feature_version_id: number;
  status: string;
  input_count: number;
  output_count: number;
  valid_count: number;
  missing_count: number;
  invalid_count: number;
  quality_summary: JsonObject;
  duration_ms: number;
  error_code: string;
  error_message: string;
  started_at?: string;
  finished_at?: string;
}

export interface FeatureRunSubject {
  run_id: string;
  security_id: number;
  symbol_snapshot: string;
  exchange_snapshot: string;
  asset_type_snapshot: string;
  included_reason: string;
}

export interface FeatureRunDetail {
  run: FeatureRun;
  items: FeatureRunItem[];
  subjects?: FeatureRunSubject[];
}

export interface FeatureNumericValue {
  run_id: string;
  feature_version_id: number;
  security_id: number;
  observed_at: string;
  value: number | null;
  value_status: string;
  quality_flags: JsonObject;
  source_max_available_at?: string;
  computed_at: string;
}

export interface FeatureRegistryRow {
  definition: FeatureDefinition;
  published_versions: FeatureVersion[];
  latest_published_version?: FeatureVersion;
  availability: FeatureAvailability;
}

export interface DefinitionFilters {
  status?: string;
  category?: string;
  owner?: string;
  limit?: number;
  offset?: number;
}

export interface RunFilters {
  status?: string;
  producer_service?: string;
  feature_version_id?: number;
  backfill_id?: string;
  limit?: number;
  offset?: number;
}

export interface ValueFilters {
  feature_code?: string;
  version?: number;
  feature_version_id?: number;
  security_ids?: number[];
  observed_from?: string;
  observed_to?: string;
  run_id?: string;
  limit?: number;
  offset?: number;
}

export interface FeatureReference {
  code: string;
  version: number;
}

export interface FeatureComputeRequest {
  features: FeatureReference[];
  security_ids: number[];
  as_of_time: string;
  data_cutoff_time: string;
  market: string;
  source_profile: string;
  trigger_type: 'manual';
  idempotency_key?: string;
  parameters: JsonObject;
  force: boolean;
  retry_of_run_id?: string;
}

export interface FeatureComputeResponse {
  accepted: boolean;
  reused: boolean;
  run_id: string;
  status: string;
  request_fingerprint: string;
}

export interface FeaturePlatformErrorView {
  code: string;
  message: string;
  status?: number;
}
