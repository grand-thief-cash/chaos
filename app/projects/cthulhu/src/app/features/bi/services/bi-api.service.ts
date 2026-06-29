import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { BIMetricsMetaResponse } from '../models/bi-legacy.models';

const BASE_URL = environment.artemisApiBase;

@Injectable({ providedIn: 'root' })
export class BiApiService {
  private readonly http = inject(HttpClient);

  getMetricDefinitions(): Observable<BIMetricsMetaResponse> {
    return this.http.get<BIMetricsMetaResponse>(`${BASE_URL}/bi/meta/metrics`);
  }
}
