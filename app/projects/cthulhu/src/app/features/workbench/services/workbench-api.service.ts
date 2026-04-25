import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  SourcesResponse,
  WorkbenchStrategiesResponse,
  WorkbenchRunRequest,
  BacktestResult,
  MarketDataResponse,
  IndicatorsListResponse,
  IndicatorsCalcRequest,
  IndicatorsCalcResponse,
  DataOptionsResponse,
  IndustryCategoriesResponse,
  IndustryConstituentsResponse,
  IndustryDailyResponse,
} from '../models/workbench.model';
import { environment } from '../../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class WorkbenchApiService {
  private API_BASE = environment.artemisApiBase;

  constructor(private http: HttpClient) {}

  getSources(): Observable<SourcesResponse> {
    return this.http.get<SourcesResponse>(`${this.API_BASE}/workbench/sources`);
  }

  getDataOptions(): Observable<DataOptionsResponse> {
    return this.http.get<DataOptionsResponse>(`${this.API_BASE}/workbench/data-options`);
  }

  getStrategies(): Observable<WorkbenchStrategiesResponse> {
    return this.http.get<WorkbenchStrategiesResponse>(`${this.API_BASE}/workbench/strategies`);
  }

  runBacktest(req: WorkbenchRunRequest): Observable<BacktestResult> {
    return this.http.post<BacktestResult>(`${this.API_BASE}/workbench/run`, req);
  }

  getMarketData(
    symbol: string,
    startDate: string,
    endDate: string,
    period = 'daily',
    adjust = 'nf',
    assetType = 'stock',
    market = 'zh_a',
    source?: string,
  ): Observable<MarketDataResponse> {
    let params = new HttpParams()
      .set('symbol', symbol)
      .set('start_date', startDate)
      .set('end_date', endDate)
      .set('period', period)
      .set('adjust', adjust)
      .set('asset_type', assetType)
      .set('market', market);
    if (source) {
      params = params.set('source', source);
    }
    return this.http.get<MarketDataResponse>(`${this.API_BASE}/workbench/market-data`, { params });
  }

  getAvailableIndicators(): Observable<IndicatorsListResponse> {
    return this.http.get<IndicatorsListResponse>(`${this.API_BASE}/workbench/indicators`);
  }

  calculateIndicators(req: IndicatorsCalcRequest): Observable<IndicatorsCalcResponse> {
    return this.http.post<IndicatorsCalcResponse>(`${this.API_BASE}/workbench/indicators`, req);
  }

  // ── Industry Explorer ──

  getIndustryCategories(params?: {
    source?: string; level?: number; parent_code?: string; name?: string;
    page?: number; page_size?: number;
  }): Observable<IndustryCategoriesResponse> {
    let httpParams = new HttpParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') {
          httpParams = httpParams.set(k, String(v));
        }
      });
    }
    return this.http.get<IndustryCategoriesResponse>(
      `${this.API_BASE}/workbench/industry/categories`, { params: httpParams },
    );
  }

  getIndustryConstituents(indexCode: string, page = 1, pageSize = 500): Observable<IndustryConstituentsResponse> {
    const params = new HttpParams()
      .set('index_code', indexCode)
      .set('page', page)
      .set('page_size', pageSize);
    return this.http.get<IndustryConstituentsResponse>(
      `${this.API_BASE}/workbench/industry/constituents`, { params },
    );
  }

  getIndustriesByStock(conCode: string): Observable<IndustryConstituentsResponse> {
    const params = new HttpParams().set('con_code', conCode);
    return this.http.get<IndustryConstituentsResponse>(
      `${this.API_BASE}/workbench/industry/by-stock`, { params },
    );
  }

  getIndustryDaily(indexCode: string, startDate: string, endDate: string): Observable<IndustryDailyResponse> {
    const params = new HttpParams()
      .set('index_code', indexCode)
      .set('start_date', startDate)
      .set('end_date', endDate);
    return this.http.get<IndustryDailyResponse>(
      `${this.API_BASE}/workbench/industry/daily`, { params },
    );
  }
}
