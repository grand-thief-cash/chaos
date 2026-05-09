import {inject, Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {
  WriteBufferStatus,
  CatalogOverview,
  TableCatalogEntry,
  TableDetail,
  StorageInfo,
  GraphCatalogOverview
} from '../models/phoenixa.models';
import {environment} from '../../../../environments/environment';

const BASE_URL = environment.phoenixAApiBase;

@Injectable({
  providedIn: 'root'
})
export class PhoenixAService {
  private http = inject(HttpClient);

  getBufferStats(): Observable<WriteBufferStatus> {
    return this.http.get<WriteBufferStatus>(`${BASE_URL}/api/v2/buffer/stats`);
  }

  getCatalogOverview(refresh = false): Observable<CatalogOverview> {
    const params = refresh ? '?refresh=true' : '';
    return this.http.get<CatalogOverview>(`${BASE_URL}/api/v2/catalog/overview${params}`);
  }

  getCatalogTables(domain?: string, refresh = false): Observable<{tables: TableCatalogEntry[]}> {
    const q = new URLSearchParams();
    if (domain) q.set('domain', domain);
    if (refresh) q.set('refresh', 'true');
    const qs = q.toString() ? `?${q.toString()}` : '';
    return this.http.get<{tables: TableCatalogEntry[]}>(`${BASE_URL}/api/v2/catalog/tables${qs}`);
  }

  getTableDetail(schema: string, table: string, refresh = false): Observable<TableDetail> {
    const params = refresh ? '?refresh=true' : '';
    return this.http.get<TableDetail>(`${BASE_URL}/api/v2/catalog/tables/${schema}/${table}${params}`);
  }

  getStorageInfo(): Observable<StorageInfo> {
    return this.http.get<StorageInfo>(`${BASE_URL}/api/v2/catalog/storage`);
  }

  getGraphCatalog(): Observable<GraphCatalogOverview> {
    return this.http.get<GraphCatalogOverview>(`${BASE_URL}/api/v2/catalog/graph`);
  }
}

