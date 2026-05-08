import {inject, Injectable} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {Observable} from 'rxjs';
import {RegimeComputeResult, RegimeFeatures, RegimeResult} from '../models/regime.models';
import {environment} from '../../../../environments/environment';

const BASE_URL = environment.artemisApiBase;

@Injectable({providedIn: 'root'})
export class RegimeService {
  private http = inject(HttpClient);

  /** POST /regime/compute – compute single-day regime */
  compute(tradeDate: string, market: string = 'zh_a'): Observable<RegimeResult> {
    const params = new HttpParams().set('trade_date', tradeDate).set('market', market);
    return this.http.post<RegimeResult>(`${BASE_URL}/regime/compute`, null, {params});
  }

  /** POST /regime/backfill – batch backfill */
  backfill(tradingDates: string[]): Observable<RegimeComputeResult> {
    return this.http.post<RegimeComputeResult>(`${BASE_URL}/regime/backfill`, tradingDates);
  }

  /** GET /regime/current – latest regime */
  getCurrent(market: string = 'zh_a'): Observable<RegimeResult> {
    const params = new HttpParams().set('market', market);
    return this.http.get<RegimeResult>(`${BASE_URL}/regime/current`, {params});
  }

  /** GET /regime/history – history list */
  getHistory(limit: number = 60): Observable<RegimeResult[]> {
    const params = new HttpParams().set('limit', limit.toString());
    return this.http.get<RegimeResult[]>(`${BASE_URL}/regime/history`, {params});
  }

  /** GET /regime/features – features for a trade date */
  getFeatures(tradeDate: string): Observable<RegimeFeatures> {
    const params = new HttpParams().set('trade_date', tradeDate);
    return this.http.get<RegimeFeatures>(`${BASE_URL}/regime/features`, {params});
  }
}

