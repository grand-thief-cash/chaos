import {inject, Injectable} from '@angular/core';
import {HttpContext, HttpClient, HttpParams} from '@angular/common/http';
import {Observable, of} from 'rxjs';
import {catchError} from 'rxjs/operators';
import {environment} from '../../../../environments/environment';
import {SKIP_GLOBAL_ERROR_NOTIFICATION} from '../../../core/errors/error-notification.interceptor';
import {
  AtlasList, ExtractionBatchRequest, ExtractionBatchResponse, ExtractionRun,
  GovernanceRecord, GraphStats, KnowledgeEntity,
  SampleCategoryResult, SampleRun, SampleRunRequest,
} from '../models/atlas.models';

@Injectable({providedIn: 'root'})
export class AtlasApiService {
  private http = inject(HttpClient);
  private atlas = environment.atlasApiBase;
  private phoenix = environment.phoenixAApiBase;

  extractionRuns(status = ''): Observable<AtlasList<ExtractionRun>> {
    const params = status ? new HttpParams().set('status', status) : undefined;
    return this.http.get<AtlasList<ExtractionRun>>(
      `${this.phoenix}/api/v1/atlas-kg/extraction-runs`, {params}
    );
  }
  startExtractionBatch(
    payload: ExtractionBatchRequest
  ): Observable<ExtractionBatchResponse> {
    return this.http.post<ExtractionBatchResponse>(
      `${this.atlas}/api/v1/atlas-kg/extraction-batches`,
      payload,
    );
  }
  governance(kind: string): Observable<AtlasList<GovernanceRecord>> {
    return this.http.get<AtlasList<GovernanceRecord>>(
      `${this.phoenix}/api/v1/atlas-kg/governance/${kind}`
    );
  }
  reviewDiscovery(runId: string, payload: unknown): Observable<any> {
    return this.http.put(
      `${this.atlas}/api/v1/atlas-kg/discovery-runs/${runId}/review`, payload
    );
  }
  publishSemantic(runId: string, version: string): Observable<any> {
    return this.http.post(`${this.atlas}/api/v1/atlas-kg/semantic-versions:publish`, {
      discovery_run_id: runId, version
    });
  }
  runCrosswalk(sourceScheme: string, targetScheme: string): Observable<any> {
    return this.http.post(`${this.atlas}/api/v1/atlas-kg/crosswalk-runs`, {
      source_scheme: sourceScheme, target_scheme: targetScheme
    });
  }
  runRequiredCrosswalks(): Observable<any> {
    return this.http.post(
      `${this.atlas}/api/v1/atlas-kg/crosswalk-runs:required`,
      {},
    );
  }
  reviewCrosswalk(runId: string, payload: unknown): Observable<any> {
    return this.http.put(
      `${this.atlas}/api/v1/atlas-kg/crosswalk-runs/${runId}/review`,
      payload,
    );
  }
  publishCrosswalk(runId: string, version: string): Observable<any> {
    return this.http.post(
      `${this.atlas}/api/v1/atlas-kg/crosswalk-semantic-versions:publish`,
      {crosswalk_run_id: runId, version},
    );
  }
  entities(query = ''): Observable<AtlasList<KnowledgeEntity>> {
    const params = query ? new HttpParams().set('q', query) : undefined;
    return this.http.get<AtlasList<KnowledgeEntity>>(
      `${this.phoenix}/api/v1/atlas-kg/entities`, {params}
    );
  }
  saveEntities(entities: KnowledgeEntity[]): Observable<{count: number}> {
    return this.http.post<{count: number}>(
      `${this.phoenix}/api/v1/atlas-kg/entities:batch`,
      entities,
    );
  }
  graphStats(): Observable<GraphStats> {
    // The graph service may not be deployed in every environment; a 404 is
    // expected there, not an error worth surfacing in the global banner or
    // the overview page. Suppress the global notification and fall back to
    // empty stats so the overview cards render zeros instead of an error.
    return this.http.get<GraphStats>(
      `${this.phoenix}/api/v1/atlas-graph/stats`,
      {context: new HttpContext().set(SKIP_GLOBAL_ERROR_NOTIFICATION, true)},
    ).pipe(
      catchError(() => of({entities: 0, claims: 0} as GraphStats)),
    );
  }
  graphSearch(query: string): Observable<AtlasList<any>> {
    return this.http.get<AtlasList<any>>(`${this.phoenix}/api/v1/atlas-graph/search`, {
      params: new HttpParams().set('q', query)
    });
  }
  ask(question: string): Observable<any> {
    return this.http.post(`${this.atlas}/api/v1/atlas-kg/query`, {question});
  }
  companyReview(companyName: string): Observable<any> {
    return this.http.post(`${this.atlas}/api/v1/atlas-kg/company-reviews`, {
      company_name: companyName,
    });
  }

  createSampleRun(payload: SampleRunRequest): Observable<{sample_run_id: string; accepted: boolean; cronjob_run_id: number | null}> {
    return this.http.post<{sample_run_id: string; accepted: boolean; cronjob_run_id: number | null}>(
      `${this.atlas}/api/v1/atlas-kg/sample-runs`, payload,
    );
  }
  getSampleRun(runId: string): Observable<SampleRun> {
    return this.http.get<SampleRun>(`${this.atlas}/api/v1/atlas-kg/sample-runs/${runId}`);
  }
  listSampleRuns(status: string): Observable<AtlasList<SampleRun>> {
    const params = status ? new HttpParams().set('status', status) : undefined;
    return this.http.get<AtlasList<SampleRun>>(
      `${this.atlas}/api/v1/atlas-kg/sample-runs`, {params}
    );
  }
  listSampleCategoryResults(runId: string): Observable<AtlasList<SampleCategoryResult>> {
    return this.http.get<AtlasList<SampleCategoryResult>>(
      `${this.atlas}/api/v1/atlas-kg/sample-runs/${runId}/category-results`,
    );
  }
  updateSampleFieldSummary(
    runId: string, reportType: string, fieldSummary: unknown,
  ): Observable<{updated: boolean}> {
    return this.http.put<{updated: boolean}>(
      `${this.atlas}/api/v1/atlas-kg/sample-runs/${runId}/category-results/${reportType}/field-summary`,
      {field_summary: fieldSummary},
    );
  }
}
