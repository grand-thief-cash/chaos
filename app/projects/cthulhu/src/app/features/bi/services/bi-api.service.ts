import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { BIDashboardResponse, BIDupontResponse, BIInsightResponse, BIMetricsMetaResponse, BIPeerComparisonRequest, BIPeerComparisonResponse, BIQualityResponse, BISecuritySearchResponse } from '../models/bi.models';

const BASE_URL = environment.artemisApiBase;

@Injectable({ providedIn: 'root' })
export class BiApiService {
  private readonly http = inject(HttpClient);

  getCompanyDashboard(symbol: string, asOfDate: string, market: string = 'zh_a', source: string = 'amazing_data'): Observable<BIDashboardResponse> {
    const params = new HttpParams()
      .set('as_of_date', asOfDate)
      .set('market', market)
      .set('source', source);
    return this.http.get<BIDashboardResponse>(`${BASE_URL}/bi/financial/company/${symbol}/dashboard`, { params });
  }

  getCompanyDupont(symbol: string, asOfDate: string, market: string = 'zh_a', source: string = 'amazing_data'): Observable<BIDupontResponse> {
    const params = new HttpParams()
      .set('as_of_date', asOfDate)
      .set('market', market)
      .set('source', source);
    return this.http.get<BIDupontResponse>(`${BASE_URL}/bi/financial/company/${symbol}/dupont`, { params });
  }

  getCompanyQuality(symbol: string, asOfDate: string, market: string = 'zh_a', source: string = 'amazing_data'): Observable<BIQualityResponse> {
    const params = new HttpParams()
      .set('as_of_date', asOfDate)
      .set('market', market)
      .set('source', source);
    return this.http.get<BIQualityResponse>(`${BASE_URL}/bi/financial/company/${symbol}/quality`, { params });
  }

  getCompanyInsight(symbol: string, asOfDate: string, market: string = 'zh_a', source: string = 'amazing_data'): Observable<BIInsightResponse> {
    const params = new HttpParams()
      .set('as_of_date', asOfDate)
      .set('market', market)
      .set('source', source);
    return this.http.get<BIInsightResponse>(`${BASE_URL}/bi/financial/company/${symbol}/insight`, { params });
  }

  searchSecurities(query: string, market: string = 'zh_a', limit: number = 20): Observable<BISecuritySearchResponse> {
    const params = new HttpParams()
      .set('query', query)
      .set('market', market)
      .set('limit', String(limit));
    return this.http.get<BISecuritySearchResponse>(`${BASE_URL}/bi/search/securities`, { params });
  }

  getPeerComparison(req: BIPeerComparisonRequest): Observable<BIPeerComparisonResponse> {
    return this.http.post<BIPeerComparisonResponse>(`${BASE_URL}/bi/financial/peer-comparison`, req);
  }

  getMetricDefinitions(): Observable<BIMetricsMetaResponse> {
    return this.http.get<BIMetricsMetaResponse>(`${BASE_URL}/bi/meta/metrics`);
  }
}


