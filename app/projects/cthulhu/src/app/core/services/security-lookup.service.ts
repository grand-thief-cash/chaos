import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';

/**
 * A security in the unified registry (phoenixA security_registry). Returned
 * by the general /securities search; security_id is the internal identity
 * handed to downstream endpoints (e.g. /bi/dupont/{security_id}).
 */
export interface SecuritySearchItem {
  security_id: number;
  symbol: string;
  asset_type: string;
  market: string;
  exchange: string;
  name: string;
  full_name?: string | null;
  status: string;
  list_date?: string | null;
  delist_date?: string | null;
}

export interface SecuritySearchResponse {
  items: SecuritySearchItem[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * General securities lookup - shared across features (BI, workbench, ...).
 * cthulhu -> artemis /securities/* -> phoenixA /api/v2/securities/*.
 *
 * This service only does HTTP + data shaping. Debounce / cancellation /
 * min-length gating live in the search-input component so the wire format is
 * reusable by any caller.
 */
@Injectable({ providedIn: 'root' })
export class SecurityLookupService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.artemisApiBase;

  /** Typeahead search by name/symbol (q: symbol exact OR name contains). */
  search(
    term: string,
    opts: { market?: string; asset_type?: string; limit?: number; offset?: number } = {},
  ): Observable<SecuritySearchResponse> {
    let params = new HttpParams()
      .set('q', term)
      .set('market', opts.market ?? 'zh_a')
      .set('asset_type', opts.asset_type ?? 'stock')
      .set('limit', String(opts.limit ?? 20))
      .set('offset', String(opts.offset ?? 0));
    return this.http.get<SecuritySearchResponse>(`${this.base}/securities`, { params });
  }

  /** Fetch one security by id. */
  getById(securityId: number): Observable<SecuritySearchItem> {
    return this.http.get<SecuritySearchItem>(`${this.base}/securities/${securityId}`);
  }
}
