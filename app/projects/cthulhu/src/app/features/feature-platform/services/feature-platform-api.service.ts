import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { SKIP_GLOBAL_ERROR_NOTIFICATION } from '../../../core/errors/error-notification.interceptor';
import { environment } from '../../../../environments/environment';
import {
  DefinitionFilters,
  BackfillFilters,
  FeatureBackfillDetail,
  FeatureBackfillJob,
  FeatureBackfillPreview,
  FeatureBackfillRequest,
  FeatureAvailability,
  FeatureComputeRequest,
  FeatureComputeResponse,
  FeatureDefinition,
  FeatureDefinitionDetail,
  FeatureLifecycleEvent,
  FeatureLifecycleTransitionRequest,
  FeatureLineage,
  FeatureNumericStats,
  FeatureNumericStatsRequest,
  ManifestCatalogResponse,
  ManifestValidationResponse,
  FeatureNumericValue,
  FeaturePreviewRequest,
  FeaturePreviewResponse,
  FeaturePurgeDetail,
  FeaturePurgePreviewRequest,
  FeaturePurgePreviewResponse,
  FeaturePurgeSubmitRequest,
  FeatureRun,
  FeatureRunDetail,
  FeatureScopeRequest,
  FeatureScopeResolution,
  PaginatedResponse,
  RegistrySyncPreviewResponse,
  RegistrySyncRequest,
  RegistrySyncSelection,
  PurgeFilters,
  RunFilters,
  ValueFilters,
} from '../models/feature-platform.models';

@Injectable({ providedIn: 'root' })
export class FeaturePlatformApiService {
  private readonly http = inject(HttpClient);
  private readonly phoenixBase = `${environment.phoenixAApiBase}/api/v2/features`;
  private readonly artemisBase = `${environment.artemisApiBase}/features`;

  listDefinitions(filters: DefinitionFilters = {}): Observable<PaginatedResponse<FeatureDefinition>> {
    return this.http.get<PaginatedResponse<FeatureDefinition>>(
      `${this.phoenixBase}/definitions`,
      { params: this.params(filters), context: this.localErrorContext() },
    );
  }

  getDefinition(featureCode: string): Observable<FeatureDefinitionDetail> {
    return this.http.get<FeatureDefinitionDetail>(
      `${this.phoenixBase}/definitions/${encodeURIComponent(featureCode)}`,
      { context: this.localErrorContext() },
    );
  }

  getLineage(featureCode: string): Observable<FeatureLineage> {
    return this.http.get<FeatureLineage>(
      `${this.phoenixBase}/lineage/${encodeURIComponent(featureCode)}`,
      { context: this.localErrorContext() },
    );
  }

  getAvailability(featureCode: string, sourceProfile = 'default'): Observable<FeatureAvailability> {
    return this.http.get<FeatureAvailability>(
      `${this.phoenixBase}/availability/${encodeURIComponent(featureCode)}`,
      {
        params: new HttpParams().set('source_profile', sourceProfile),
        context: this.localErrorContext(),
      },
    );
  }

  listRuns(filters: RunFilters = {}): Observable<PaginatedResponse<FeatureRun>> {
    return this.http.get<PaginatedResponse<FeatureRun>>(
      `${this.phoenixBase}/runs`,
      { params: this.params(filters), context: this.localErrorContext() },
    );
  }

  getRun(runId: string, includeSubjects = true): Observable<FeatureRunDetail> {
    return this.http.get<FeatureRunDetail>(
      `${this.phoenixBase}/runs/${encodeURIComponent(runId)}`,
      {
        params: new HttpParams().set('include_subjects', String(includeSubjects)),
        context: this.localErrorContext(),
      },
    );
  }

  queryValues(filters: ValueFilters, latest = false): Observable<PaginatedResponse<FeatureNumericValue>> {
    const path = latest ? 'values/numeric/latest' : 'values/numeric';
    const values = { ...filters, security_ids: filters.security_ids?.join(',') };
    return this.http.get<PaginatedResponse<FeatureNumericValue>>(
      `${this.phoenixBase}/${path}`,
      { params: this.params(values), context: this.localErrorContext() },
    );
  }

  numericValueStats(request: FeatureNumericStatsRequest): Observable<FeatureNumericStats> {
    return this.http.post<FeatureNumericStats>(
      `${this.phoenixBase}/values/numeric:stats`,
      request,
      { context: this.localErrorContext() },
    );
  }

  compute(request: FeatureComputeRequest): Observable<FeatureComputeResponse> {
    return this.http.post<FeatureComputeResponse>(
      `${this.artemisBase}/compute`,
      request,
      { context: this.localErrorContext() },
    );
  }

  resolveScope(request: FeatureScopeRequest): Observable<FeatureScopeResolution> {
    return this.http.post<FeatureScopeResolution>(
      `${this.artemisBase}/scope:resolve`,
      request,
      { context: this.localErrorContext() },
    );
  }

  preview(request: FeaturePreviewRequest): Observable<FeaturePreviewResponse> {
    return this.http.post<FeaturePreviewResponse>(
      `${this.artemisBase}/preview`,
      request,
      { context: this.localErrorContext() },
    );
  }

  previewBackfill(request: FeatureBackfillRequest): Observable<FeatureBackfillPreview> {
    return this.http.post<FeatureBackfillPreview>(
      `${this.artemisBase}/backfills:preview`,
      request,
      { context: this.localErrorContext() },
    );
  }

  createBackfill(request: FeatureBackfillRequest): Observable<FeatureBackfillDetail> {
    return this.http.post<FeatureBackfillDetail>(
      `${this.artemisBase}/backfills`,
      request,
      { context: this.localErrorContext() },
    );
  }

  listBackfills(filters: BackfillFilters = {}): Observable<PaginatedResponse<FeatureBackfillJob>> {
    return this.http.get<PaginatedResponse<FeatureBackfillJob>>(
      `${this.artemisBase}/backfills`,
      { params: this.params(filters), context: this.localErrorContext() },
    );
  }

  getBackfill(backfillId: string, sourceProfile = 'default'): Observable<FeatureBackfillDetail> {
    return this.http.get<FeatureBackfillDetail>(
      `${this.artemisBase}/backfills/${encodeURIComponent(backfillId)}`,
      {
        params: new HttpParams().set('source_profile', sourceProfile),
        context: this.localErrorContext(),
      },
    );
  }

  cancelBackfill(backfillId: string, sourceProfile = 'default'): Observable<Record<string, unknown>> {
    return this.http.post<Record<string, unknown>>(
      `${this.artemisBase}/backfills/${encodeURIComponent(backfillId)}:cancel`,
      {},
      {
        params: new HttpParams().set('source_profile', sourceProfile),
        context: this.localErrorContext(),
      },
    );
  }

  retryFailedBackfill(backfillId: string, sourceProfile = 'default'): Observable<{ runs: FeatureRun[]; count: number }> {
    return this.http.post<{ runs: FeatureRun[]; count: number }>(
      `${this.artemisBase}/backfills/${encodeURIComponent(backfillId)}:retry-failed`,
      {},
      {
        params: new HttpParams().set('source_profile', sourceProfile),
        context: this.localErrorContext(),
      },
    );
  }

  previewPurge(request: FeaturePurgePreviewRequest): Observable<FeaturePurgePreviewResponse> {
    return this.http.post<FeaturePurgePreviewResponse>(
      `${this.phoenixBase}/purges:preview`,
      request,
      { context: this.localErrorContext() },
    );
  }

  submitPurge(request: FeaturePurgeSubmitRequest): Observable<FeaturePurgeDetail> {
    return this.http.post<FeaturePurgeDetail>(
      `${this.phoenixBase}/purges`,
      request,
      { context: this.localErrorContext() },
    );
  }

  listPurges(filters: PurgeFilters = {}): Observable<PaginatedResponse<FeaturePurgeDetail['job']>> {
    return this.http.get<PaginatedResponse<FeaturePurgeDetail['job']>>(
      `${this.phoenixBase}/purges`,
      { params: this.params(filters), context: this.localErrorContext() },
    );
  }

  getPurge(purgeId: string): Observable<FeaturePurgeDetail> {
    return this.http.get<FeaturePurgeDetail>(
      `${this.phoenixBase}/purges/${encodeURIComponent(purgeId)}`,
      { context: this.localErrorContext() },
    );
  }

  cancelPurge(purgeId: string): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(
      `${this.phoenixBase}/purges/${encodeURIComponent(purgeId)}:cancel`,
      {},
      { context: this.localErrorContext() },
    );
  }

  getExecution(runId: string, sourceProfile = 'default'): Observable<FeatureRunDetail> {
    return this.http.get<FeatureRunDetail>(
      `${this.artemisBase}/executions/${encodeURIComponent(runId)}`,
      {
        params: new HttpParams().set('source_profile', sourceProfile),
        context: this.localErrorContext(),
      },
    );
  }

  getManifestCatalog(
    sourceProfile = 'default',
    checkEntrypoints = true,
  ): Observable<ManifestCatalogResponse> {
    return this.http.get<ManifestCatalogResponse>(
      `${this.artemisBase}/manifests/catalog`,
      {
        params: new HttpParams()
          .set('source_profile', sourceProfile)
          .set('check_entrypoints', String(checkEntrypoints)),
        context: this.localErrorContext(),
      },
    );
  }

  validateManifests(
    request: RegistrySyncSelection = {},
  ): Observable<ManifestValidationResponse> {
    return this.http.post<ManifestValidationResponse>(
      `${this.artemisBase}/manifests/validate`,
      request,
      { context: this.localErrorContext() },
    );
  }

  previewRegistrySync(
    request: RegistrySyncSelection = {},
  ): Observable<RegistrySyncPreviewResponse> {
    return this.http.post<RegistrySyncPreviewResponse>(
      `${this.artemisBase}/registry/sync:preview`,
      request,
      { context: this.localErrorContext() },
    );
  }

  syncRegistry(request: RegistrySyncRequest): Observable<Record<string, unknown>> {
    return this.http.post<Record<string, unknown>>(
      `${this.artemisBase}/registry/sync`,
      request,
      { context: this.localErrorContext() },
    );
  }

  publishVersion(
    featureCode: string,
    version: number,
    request: FeatureLifecycleTransitionRequest,
  ): Observable<{ status: string; version: number; event: FeatureLifecycleEvent }> {
    return this.http.post<{ status: string; version: number; event: FeatureLifecycleEvent }>(
      `${this.phoenixBase}/definitions/${encodeURIComponent(featureCode)}/versions/${version}:publish`,
      request,
      { context: this.localErrorContext() },
    );
  }

  deprecateVersion(
    featureCode: string,
    version: number,
    request: FeatureLifecycleTransitionRequest,
  ): Observable<{ status: string; version: number; event: FeatureLifecycleEvent }> {
    return this.http.post<{ status: string; version: number; event: FeatureLifecycleEvent }>(
      `${this.phoenixBase}/definitions/${encodeURIComponent(featureCode)}/versions/${version}:deprecate`,
      request,
      { context: this.localErrorContext() },
    );
  }

  listLifecycleEvents(
    featureCode: string,
    limit = 100,
  ): Observable<{ items: FeatureLifecycleEvent[]; total: number }> {
    return this.http.get<{ items: FeatureLifecycleEvent[]; total: number }>(
      `${this.phoenixBase}/definitions/${encodeURIComponent(featureCode)}/lifecycle-events`,
      {
        params: new HttpParams().set('limit', String(limit)),
        context: this.localErrorContext(),
      },
    );
  }

  private localErrorContext(): HttpContext {
    return new HttpContext().set(SKIP_GLOBAL_ERROR_NOTIFICATION, true);
  }

  private params(values: object): HttpParams {
    let params = new HttpParams();
    Object.entries(values).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, String(value));
      }
    });
    return params;
  }
}
