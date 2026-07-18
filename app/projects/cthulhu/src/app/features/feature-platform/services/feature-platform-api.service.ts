import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import {
  DefinitionFilters,
  FeatureAvailability,
  FeatureComputeRequest,
  FeatureComputeResponse,
  FeatureDefinition,
  FeatureDefinitionDetail,
  FeatureLineage,
  FeatureNumericValue,
  FeatureRun,
  FeatureRunDetail,
  PaginatedResponse,
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
      { params: this.params(filters) },
    );
  }

  getDefinition(featureCode: string): Observable<FeatureDefinitionDetail> {
    return this.http.get<FeatureDefinitionDetail>(
      `${this.phoenixBase}/definitions/${encodeURIComponent(featureCode)}`,
    );
  }

  getLineage(featureCode: string): Observable<FeatureLineage> {
    return this.http.get<FeatureLineage>(
      `${this.phoenixBase}/lineage/${encodeURIComponent(featureCode)}`,
    );
  }

  getAvailability(featureCode: string, sourceProfile = 'default'): Observable<FeatureAvailability> {
    return this.http.get<FeatureAvailability>(
      `${this.phoenixBase}/availability/${encodeURIComponent(featureCode)}`,
      { params: new HttpParams().set('source_profile', sourceProfile) },
    );
  }

  listRuns(filters: RunFilters = {}): Observable<PaginatedResponse<FeatureRun>> {
    return this.http.get<PaginatedResponse<FeatureRun>>(
      `${this.phoenixBase}/runs`,
      { params: this.params(filters) },
    );
  }

  getRun(runId: string, includeSubjects = true): Observable<FeatureRunDetail> {
    return this.http.get<FeatureRunDetail>(
      `${this.phoenixBase}/runs/${encodeURIComponent(runId)}`,
      { params: new HttpParams().set('include_subjects', String(includeSubjects)) },
    );
  }

  queryValues(filters: ValueFilters, latest = false): Observable<PaginatedResponse<FeatureNumericValue>> {
    const path = latest ? 'values/numeric/latest' : 'values/numeric';
    const values = { ...filters, security_ids: filters.security_ids?.join(',') };
    return this.http.get<PaginatedResponse<FeatureNumericValue>>(
      `${this.phoenixBase}/${path}`,
      { params: this.params(values) },
    );
  }

  compute(request: FeatureComputeRequest): Observable<FeatureComputeResponse> {
    return this.http.post<FeatureComputeResponse>(`${this.artemisBase}/compute`, request);
  }

  getExecution(runId: string, sourceProfile = 'default'): Observable<FeatureRunDetail> {
    return this.http.get<FeatureRunDetail>(
      `${this.artemisBase}/executions/${encodeURIComponent(runId)}`,
      { params: new HttpParams().set('source_profile', sourceProfile) },
    );
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
