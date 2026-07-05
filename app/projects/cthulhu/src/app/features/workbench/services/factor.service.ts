import {inject, Injectable} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {Observable} from 'rxjs';
import {FactorAvailabilityResponse, FactorComputeResult, FactorMeta, FactorRankItem, FactorSnapshot} from '../models/factor.models';
import {environment} from '../../../../environments/environment';

const BASE_URL = environment.artemisApiBase;

@Injectable({providedIn: 'root'})
export class FactorService {
  private http = inject(HttpClient);

  private withOptionalSource(params: HttpParams, source?: string): HttpParams {
    if (source) {
      return params.set('source', source);
    }
    return params;
  }

  /** GET /factors/meta – list all registered factors */
  getMeta(): Observable<FactorMeta[]> {
    return this.http.get<FactorMeta[]>(`${BASE_URL}/factors/meta`);
  }

  /** GET /factors/availability – factor availability analysis */
  getAvailability(refresh: boolean = false, source?: string): Observable<FactorAvailabilityResponse> {
    const params = this.withOptionalSource(new HttpParams().set('refresh', String(refresh)), source);
    return this.http.get<FactorAvailabilityResponse>(`${BASE_URL}/factors/availability`, {params});
  }

  /** POST /factors/compute/full – trigger full computation */
  computeFull(asOfDate: string, market: string = 'zh_a', source?: string): Observable<FactorComputeResult> {
    const params = this.withOptionalSource(new HttpParams().set('as_of_date', asOfDate).set('market', market), source);
    return this.http.post<FactorComputeResult>(`${BASE_URL}/factors/compute/full`, null, {params});
  }

  /** POST /factors/compute/incremental – incremental computation */
  computeIncremental(securityIds: number[], asOfDate: string, market: string = 'zh_a', source?: string): Observable<FactorComputeResult> {
    const params = this.withOptionalSource(new HttpParams()
      .set('as_of_date', asOfDate)
      .set('market', market)
      .set('security_ids', securityIds.join(',')), source);
    return this.http.post<FactorComputeResult>(`${BASE_URL}/factors/compute/incremental`, null, {params});
  }

  /** GET /factors/snapshot – single security factor snapshot */
  getSnapshot(securityId: number, asOfDate: string, market: string = 'zh_a', source?: string): Observable<FactorSnapshot> {
    const params = this.withOptionalSource(new HttpParams().set('security_id', String(securityId)).set('as_of_date', asOfDate).set('market', market), source);
    return this.http.get<FactorSnapshot>(`${BASE_URL}/factors/snapshot`, {params});
  }

  /** GET /factors/rank – factor ranking */
  getRanking(factorName: string, asOfDate: string, market: string = 'zh_a', topN: number = 50, source?: string): Observable<FactorRankItem[]> {
    const params = this.withOptionalSource(new HttpParams()
      .set('factor_name', factorName)
      .set('as_of_date', asOfDate)
      .set('market', market)
      .set('top_n', topN.toString()), source);
    return this.http.get<FactorRankItem[]>(`${BASE_URL}/factors/rank`, {params});
  }
}

