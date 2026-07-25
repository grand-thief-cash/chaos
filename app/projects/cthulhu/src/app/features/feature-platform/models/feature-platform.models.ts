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
  latest_purge?: FeatureDataPurgeJob;
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
  nodes: FeatureGraphNode[];
  edges: FeatureGraphEdge[];
}

export interface FeatureLineage {
  feature_code: string;
  versions: FeatureLineageVersion[];
}

export interface FeatureGraphNode {
  id: string;
  node_type: 'feature_version' | 'data_field';
  label: string;
  feature_version_id?: number;
  data_field_dictionary_id?: number;
  feature_code?: string;
  version_number?: number;
  status?: string;
  root: boolean;
  execution_order?: number;
  manifest_checksum?: string;
  implementation_checksum?: string;
  dependency_checksum?: string;
}

export interface FeatureGraphEdge {
  id: string;
  source: string;
  target: string;
  kind: 'feature' | 'data_field';
}

export interface FeatureExecutionPlanSnapshot {
  schema_version: number;
  plan_checksum: string;
  root_feature_version_ids: number[];
  nodes: FeatureGraphNode[];
  edges: FeatureGraphEdge[];
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
  dependency_plan_checksum?: string;
  dependency_plan_snapshot?: FeatureExecutionPlanSnapshot;
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
  materialization_state: 'none' | 'available' | 'purging' | 'purged';
  materialized_row_count: number;
  purged_at?: string;
  last_purge_id?: string;
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

export interface ManifestCatalogError {
  code: string;
  message: string;
}

export interface ManifestCatalogItem {
  path: string;
  feature_code?: string;
  version?: number;
  identity?: string;
  validation_status: string;
  content_checksum: string;
  manifest_checksum?: string;
  plugin_status: string;
  registry_status: string;
  registry_action: string;
  registry_checksum?: string;
  changed_fields: string[];
  errors: ManifestCatalogError[];
}

export interface ManifestCatalogResponse {
  catalog_checksum: string;
  loaded_at: string;
  source_profile: string;
  count: number;
  items: ManifestCatalogItem[];
  warnings: string[];
}

export interface ManifestValidationEntry {
  feature: string;
  manifest_checksum: string;
  implementation_checksum: string;
  valid: boolean;
}

export interface ManifestValidationResponse {
  valid: boolean;
  count: number;
  manifests: ManifestValidationEntry[];
}

export interface RegistrySyncSelection {
  paths?: string[];
  check_entrypoints?: boolean;
  source_profile?: string;
}

export interface RegistrySyncRequest extends RegistrySyncSelection {
  expected_catalog_checksum: string;
}

export interface RegistrySyncChange {
  feature_code: string;
  version: number;
  identity: string;
  action: string;
  changed_fields: string[];
  current_status?: string;
  current_checksum?: string;
  desired_status: string;
  desired_checksum: string;
  code?: string;
  message?: string;
}

export interface RegistrySyncPreviewResponse {
  catalog_checksum: string;
  source_profile: string;
  changes: RegistrySyncChange[];
  blocked: RegistrySyncChange[];
  unchanged: string[];
  warnings: string[];
}

export interface FeatureLifecycleTransitionRequest {
  expected_status: 'draft' | 'published';
  expected_manifest_checksum: string;
}

export interface FeatureLifecycleEvent {
  id: number;
  feature_id: number;
  feature_version_id: number;
  action: string;
  before_status: string;
  after_status: string;
  manifest_checksum: string;
  details: JsonObject;
  created_at: string;
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

export interface FeatureNumericStatsRequest extends Omit<ValueFilters, 'limit' | 'offset'> {
  latest?: boolean;
  histogram_buckets?: number;
}

export interface FeatureNumericStats {
  count: number;
  valid_count: number;
  missing_count: number;
  invalid_count: number;
  min: number | null;
  max: number | null;
  mean: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  observed_from?: string;
  observed_to?: string;
  histogram: Array<{ lower: number; upper: number; count: number }>;
  trend: Array<{ observed_at: string; count: number; mean: number | null; min: number | null; max: number | null }>;
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

export interface FeatureUniverseScope {
  mode: 'explicit' | 'all_active';
  security_ids: number[];
}

export interface FeatureEvaluationScope {
  mode: 'point' | 'range';
  as_of_time?: string;
  start_as_of?: string;
  end_as_of?: string;
  step?: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'explicit';
  explicit_times?: string[];
}

export interface FeatureCutoffPolicy {
  mode: 'same_as_as_of' | 'lag_seconds' | 'explicit';
  seconds?: number;
  explicit?: Record<string, string>;
}

export interface FeatureScopeRequest {
  feature_refs: FeatureReference[];
  universe: FeatureUniverseScope;
  evaluation: FeatureEvaluationScope;
  data_cutoff_policy: FeatureCutoffPolicy;
  market: string;
  source_profile: string;
}

export interface FeaturePreviewRequest extends FeatureScopeRequest {
  preview_overrides: JsonObject;
}

export interface FeatureScopeResolution {
  allowed_for_preview: boolean;
  violations: string[];
  warnings: string[];
  scope: {
    universe_mode: string;
    security_count: number;
    evaluation_count: number;
    root_feature_count: number;
    dag_node_count: number;
    estimated_root_cells: number;
    estimated_execution_cells: number;
    universe_hash: string;
  };
  security_ids: number[];
  security_sample: JsonObject[];
  evaluations: Array<{ as_of_time: string; data_cutoff_time: string }>;
  plan: JsonObject;
}

export interface FeaturePreviewRow {
  feature_code: string;
  version: number;
  feature_version_id: number;
  security_id: number;
  value: number | null;
  value_status: string;
  quality_flags: JsonObject;
  source_max_available_at?: string;
}

export interface FeaturePreviewEvaluation {
  as_of_time: string;
  data_cutoff_time: string;
  rows: FeaturePreviewRow[];
  quality_summary: { valid: number; missing: number; invalid: number };
}

export interface FeaturePreviewResponse {
  preview_id: string;
  persisted: false;
  non_canonical: boolean;
  code_revision: string;
  plan_checksum: string;
  scope: FeatureScopeResolution['scope'];
  features: Array<{ feature_code: string; version: number; manifest_checksum: string }>;
  standard_config: JsonObject;
  preview_overrides: JsonObject;
  evaluations: FeaturePreviewEvaluation[];
  warnings: string[];
}

export interface FeatureBackfillRequest extends FeatureScopeRequest {
  max_concurrency: number;
  confirmation_token?: string;
}

export interface FeatureBackfillPreview {
  run_count: number;
  subject_count: number;
  estimated_execution_cells: number;
  max_concurrency: number;
  scope: FeatureScopeResolution['scope'];
  plan: FeatureExecutionPlanSnapshot;
  security_sample: JsonObject[];
  evaluations: Array<{ as_of_time: string; data_cutoff_time: string }>;
  warnings: string[];
  confirmation_token: string;
  confirmation_expires_at: string;
}

export interface FeatureBackfillJob {
  backfill_id: string;
  root_feature_version_ids: number[];
  start_as_of: string;
  end_as_of: string;
  step: string;
  expanded_as_of_times: string[];
  data_cutoff_policy: JsonObject;
  source_profile: string;
  market: string;
  universe_request: JsonObject;
  max_concurrency: number;
  status: string;
  total_count: number;
  succeeded_count: number;
  failed_count: number;
  created_at: string;
  updated_at: string;
}

export interface FeatureBackfillDetail {
  job: FeatureBackfillJob;
  runs: FeatureRun[];
}

export interface BackfillFilters {
  status?: string;
  source_profile?: string;
  market?: string;
  limit?: number;
  offset?: number;
}

export type FeaturePurgeScope = 'run' | 'feature_version' | 'feature_all_versions';

export interface FeaturePurgePreviewRequest {
  scope_type: FeaturePurgeScope;
  run_id?: string;
  feature_version_id?: number;
  feature_code?: string;
  all_versions?: boolean;
}

export interface FeatureDataPurgeJob {
  purge_id: string;
  scope_type: FeaturePurgeScope;
  criteria_snapshot: JsonObject;
  criteria_checksum: string;
  confirmation_expires_at: string;
  confirmation_text: string;
  status: string;
  estimated_rows: number;
  deleted_rows: number;
  affected_run_count: number;
  affected_version_count: number;
  affects_latest: boolean;
  observed_from?: string;
  observed_to?: string;
  started_at?: string;
  finished_at?: string;
  error_summary: JsonObject;
  created_at: string;
  updated_at: string;
}

export interface FeatureDataPurgeTarget {
  purge_id: string;
  run_id: string;
  feature_version_id: number;
  status: string;
  estimated_rows: number;
  deleted_rows: number;
  started_at?: string;
  finished_at?: string;
  error_message: string;
}

export interface FeaturePurgePreviewResponse {
  job: FeatureDataPurgeJob;
  targets: FeatureDataPurgeTarget[];
  confirmation_token: string;
  warnings: string[];
}

export interface FeaturePurgeSubmitRequest {
  purge_id: string;
  confirmation_token: string;
  confirmation_text: string;
}

export interface FeaturePurgeDetail {
  job: FeatureDataPurgeJob;
  targets: FeatureDataPurgeTarget[];
}

export interface PurgeFilters {
  status?: string;
  scope_type?: FeaturePurgeScope;
  limit?: number;
  offset?: number;
}

export interface FeatureScopeDraft {
  featureCode: string;
  version: number | null;
  universeMode: 'explicit' | 'all_active';
  securityIdsText: string;
  evaluationMode: 'point' | 'range';
  asOf: string;
  startAsOf: string;
  endAsOf: string;
  step: 'daily' | 'weekly' | 'monthly' | 'quarterly';
  cutoffMode: 'same_as_as_of' | 'lag_seconds';
  cutoffLagSeconds: number;
  market: string;
  sourceProfile: string;
}

export interface FeaturePlatformErrorView {
  code: string;
  message: string;
  status?: number;
}
