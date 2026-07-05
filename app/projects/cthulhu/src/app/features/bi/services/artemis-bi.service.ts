import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { environment } from '../../../../environments/environment';
import {
  BISecuritiesResponse,
  BIDatasetsResponse,
  BIFieldDiscoveryResponse,
  BIEnumResponse,
  BISecurityCoverageResponse,
  BIRawQueryResponse,
  BIDupontResponse,
  DupontPeriodKind,
} from '../models/bi.models';

const BASE_URL = environment.artemisApiBase;

@Injectable({ providedIn: 'root' })
export class ArtemisBiService {
  private readonly http = inject(HttpClient);
  private readonly enumCache = new Map<string, Observable<BIEnumResponse>>();

  // ─── Securities ───
  getSecurities(
    market = 'zh_a',
    limit = 20,
    offset = 0,
    exchange?: string,
    name?: string,
  ): Observable<BISecuritiesResponse> {
    let params = new HttpParams()
      .set('market', market)
      .set('limit', String(limit))
      .set('offset', String(offset));
    if (exchange) params = params.set('exchange', exchange);
    if (name) params = params.set('name', name);
    return this.http.get<BISecuritiesResponse>(`${BASE_URL}/bi/securities`, { params });
  }

  // ─── Discovery ───
  getDatasets(source?: string): Observable<BIDatasetsResponse> {
    let params = new HttpParams();
    if (source) params = params.set('source', source);
    return this.http.get<BIDatasetsResponse>(`${BASE_URL}/bi/catalog/datasets`, { params });
  }

  getDatasetFields(
    dataset: string,
    opts: { source?: string; type?: string; search?: string; include?: string } = {},
  ): Observable<BIFieldDiscoveryResponse> {
    let params = new HttpParams();
    if (opts.source) params = params.set('source', opts.source);
    if (opts.type) params = params.set('type', opts.type);
    if (opts.search) params = params.set('search', opts.search);
    if (opts.include) params = params.set('include', opts.include);
    return this.http.get<BIFieldDiscoveryResponse>(`${BASE_URL}/bi/catalog/datasets/${dataset}/fields`, { params });
  }

  getEnum(enumName: string, source?: string): Observable<BIEnumResponse> {
    const key = `${enumName}:${source ?? ''}`;
    const cached = this.enumCache.get(key);
    if (cached) return cached;
    let params = new HttpParams();
    if (source) params = params.set('source', source);
    const obs = this.http.get<BIEnumResponse>(`${BASE_URL}/bi/catalog/enums/${enumName}`, { params });
    this.enumCache.set(key, obs);
    return obs;
  }

  // ─── Per-security coverage ───
  getSecurityCoverage(securityId: number, market = 'zh_a'): Observable<BISecurityCoverageResponse> {
    const params = new HttpParams().set('market', market);
    return this.http.get<BISecurityCoverageResponse>(`${BASE_URL}/bi/catalog/securities/${securityId}/datasets/summary`, { params });
  }

  // ─── Raw queries ───
  queryFinancial(opts: {
    source: string;
    statement_type: string;
    security_id?: number;
    security_ids?: number[];
    market?: string;
    fields?: string;
    format?: string;
    period_start?: string;
    period_end?: string;
    report_type?: string;
    statement_code?: string;
    page?: number;
    page_size?: number;
  }): Observable<BIRawQueryResponse> {
    let params = new HttpParams()
      .set('format', opts.format || 'flat')
      .set('page', String(opts.page || 1))
      .set('page_size', String(opts.page_size || 100));
    if (opts.security_id != null) params = params.set('security_id', String(opts.security_id));
    if (opts.security_ids != null) params = params.set('security_ids', opts.security_ids.join(','));
    if (opts.market) params = params.set('market', opts.market);
    if (opts.fields) params = params.set('fields', opts.fields);
    if (opts.period_start) params = params.set('period_start', opts.period_start);
    if (opts.period_end) params = params.set('period_end', opts.period_end);
    if (opts.report_type) params = params.set('report_type', opts.report_type);
    if (opts.statement_code) params = params.set('statement_code', opts.statement_code);
    return this.http.get<BIRawQueryResponse>(`${BASE_URL}/bi/financial/${opts.source}/${opts.statement_type}`, { params });
  }

  queryCorporateAction(opts: {
    source: string;
    action_type: string;
    security_id?: number;
    security_ids?: number[];
    market?: string;
    fields?: string;
    format?: string;
    period_start?: string;
    period_end?: string;
    page?: number;
    page_size?: number;
  }): Observable<BIRawQueryResponse> {
    let params = new HttpParams()
      .set('format', opts.format || 'flat')
      .set('page', String(opts.page || 1))
      .set('page_size', String(opts.page_size || 100));
    if (opts.security_id != null) params = params.set('security_id', String(opts.security_id));
    if (opts.security_ids != null) params = params.set('security_ids', opts.security_ids.join(','));
    if (opts.market) params = params.set('market', opts.market);
    if (opts.fields) params = params.set('fields', opts.fields);
    if (opts.period_start) params = params.set('period_start', opts.period_start);
    if (opts.period_end) params = params.set('period_end', opts.period_end);
    return this.http.get<BIRawQueryResponse>(`${BASE_URL}/bi/corporate-action/${opts.source}/${opts.action_type}`, { params });
  }

  queryEquityStructure(opts: {
    source: string;
    security_id?: number;
    security_ids?: number[];
    market?: string;
    fields?: string;
    format?: string;
    change_start?: string;
    change_end?: string;
    current_only?: boolean;
    valid_only?: boolean;
    page?: number;
    page_size?: number;
  }): Observable<BIRawQueryResponse> {
    let params = new HttpParams()
      .set('format', opts.format || 'flat')
      .set('page', String(opts.page || 1))
      .set('page_size', String(opts.page_size || 100));
    if (opts.security_id != null) params = params.set('security_id', String(opts.security_id));
    if (opts.security_ids != null) params = params.set('security_ids', opts.security_ids.join(','));
    if (opts.market) params = params.set('market', opts.market);
    if (opts.fields) params = params.set('fields', opts.fields);
    if (opts.change_start) params = params.set('change_start', opts.change_start);
    if (opts.change_end) params = params.set('change_end', opts.change_end);
    if (opts.current_only !== undefined) params = params.set('current_only', opts.current_only ? '1' : '0');
    if (opts.valid_only !== undefined) params = params.set('valid_only', opts.valid_only ? '1' : '0');
    return this.http.get<BIRawQueryResponse>(`${BASE_URL}/bi/equity-structure/${opts.source}`, { params });
  }

  // ─── DuPont analysis (artemis-owned computation) ───
  getDupont(
    securityId: number,
    opts: {
      source?: string;
      market?: string;
      statement_code?: string;
      period_kind?: DupontPeriodKind;
      target_reporting_period?: string;
      extrapolate_q4?: boolean;
    } = {},
  ): Observable<BIDupontResponse> {
    let params = new HttpParams();
    if (opts.source) params = params.set('source', opts.source);
    if (opts.market) params = params.set('market', opts.market);
    if (opts.statement_code) params = params.set('statement_code', opts.statement_code);
    if (opts.period_kind) params = params.set('period_kind', opts.period_kind);
    if (opts.target_reporting_period) params = params.set('target_reporting_period', opts.target_reporting_period);
    if (opts.extrapolate_q4) params = params.set('extrapolate_q4', 'true');
    return this.http.get<BIDupontResponse>(`${BASE_URL}/bi/dupont/${securityId}`, { params });
  }
}
