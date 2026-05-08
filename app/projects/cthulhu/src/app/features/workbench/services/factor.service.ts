import {inject, Injectable} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {Observable} from 'rxjs';
import {FactorComputeResult, FactorMeta, FactorRankItem, FactorSnapshot} from '../models/factor.models';
import {environment} from '../../../../environments/environment';

const BASE_URL = environment.artemisApiBase;

@Injectable({providedIn: 'root'})
export class FactorService {
  private http = inject(HttpClient);

  /** GET /factors/meta – list all registered factors */
  getMeta(): Observable<FactorMeta[]> {
    return this.http.get<FactorMeta[]>(`${BASE_URL}/factors/meta`);
  }

  /** POST /factors/compute/full – trigger full computation */
  computeFull(asOfDate: string, market: string = 'zh_a'): Observable<FactorComputeResult> {
    const params = new HttpParams().set('as_of_date', asOfDate).set('market', market);
    return this.http.post<FactorComputeResult>(`${BASE_URL}/factors/compute/full`, null, {params});
  }

  /** POST /factors/compute/incremental – incremental computation */
  computeIncremental(symbols: string[], asOfDate: string, market: string = 'zh_a'): Observable<FactorComputeResult> {
    const params = new HttpParams().set('as_of_date', asOfDate).set('market', market);
    return this.http.post<FactorComputeResult>(`${BASE_URL}/factors/compute/incremental`, symbols, {params});
  }

  /** GET /factors/snapshot – single symbol factor snapshot */
  getSnapshot(symbol: string, asOfDate: string, market: string = 'zh_a'): Observable<FactorSnapshot> {
    const params = new HttpParams().set('symbol', symbol).set('as_of_date', asOfDate).set('market', market);
    return this.http.get<FactorSnapshot>(`${BASE_URL}/factors/snapshot`, {params});
  }

  /** GET /factors/rank – factor ranking */
  getRanking(factorName: string, asOfDate: string, market: string = 'zh_a', topN: number = 50): Observable<FactorRankItem[]> {
    const params = new HttpParams()
      .set('factor_name', factorName)
      .set('as_of_date', asOfDate)
      .set('market', market)
      .set('top_n', topN.toString());
    return this.http.get<FactorRankItem[]>(`${BASE_URL}/factors/rank`, {params});
  }
}

