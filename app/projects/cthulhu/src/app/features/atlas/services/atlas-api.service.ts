import {inject, Injectable} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {Observable} from 'rxjs';
import {environment} from '../../../../environments/environment';
import {
  AtlasList, ExtractionBatchRequest, ExtractionBatchResponse, ExtractionRun,
  GovernanceRecord, GraphStats, KnowledgeEntity
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
  startDiscovery(sampleSize: number, reportTypes: string[]): Observable<any> {
    return this.http.post(`${this.atlas}/api/v1/atlas-kg/discovery-runs`, {
      sample_size: sampleSize, report_types: reportTypes
    });
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
    return this.http.get<GraphStats>(`${this.phoenix}/api/v1/atlas-graph/stats`);
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
}
