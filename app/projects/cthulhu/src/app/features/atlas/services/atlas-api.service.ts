import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';

export interface GraphStats {
  node_counts: Record<string, number>;
  total_nodes: number;
  total_edges: number;
}

export interface CompanyData {
  company: Record<string, any>;
  relationships: any[];
}

export interface ChainData {
  nodes: any[];
  edges: any[];
}

export interface EventItem {
  id: number;
  event_fingerprint: string;
  entity_name: string;
  event_type: string;
  direction: string;
  time_bucket: string;
  description: string;
  severity: string;
  source_count: number;
  first_seen_at: string;
  last_seen_at: string;
  impact_triggered: boolean;
}

export interface ImpactResult {
  event: string;
  direct_impacts: any[];
  indirect_impacts: any[];
  total_affected: number;
  llm_analysis: string;
}

export interface DailyRun {
  id: number;
  run_date: string;
  docs_fetched: number;
  docs_graph_building: number;
  docs_event: number;
  events_new: number;
  events_deduped: number;
  extractions_ok: number;
  extractions_fail: number;
  impacts_generated: number;
  total_cost_usd: number;
  status: string;
  started_at: string;
  completed_at: string;
}

export interface DocumentItem {
  id: number;
  doc_id: string;
  title: string;
  doc_type: string;
  source_type: string;
  company: string;
  file_path: string;
  processed: boolean;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class AtlasApiService {
  private API = environment.atlasApiBase;

  constructor(private http: HttpClient) {}

  // ── Health ──
  health(): Observable<any> {
    return this.http.get(`${this.API}/health`);
  }

  // ── Graph ──
  getGraphStats(): Observable<GraphStats> {
    return this.http.get<GraphStats>(`${this.API}/api/v1/graph/stats`);
  }

  searchNodes(q: string, limit = 20): Observable<{ query: string; results: any[]; total: number }> {
    return this.http.get<any>(`${this.API}/api/v1/graph/search`, {
      params: new HttpParams().set('q', q).set('limit', limit),
    });
  }

  getCompany(name: string): Observable<CompanyData> {
    return this.http.get<CompanyData>(`${this.API}/api/v1/graph/company/${encodeURIComponent(name)}`);
  }

  getCompanyChain(name: string, maxHops = 3): Observable<{ company: string; chain: ChainData }> {
    return this.http.get<any>(`${this.API}/api/v1/graph/company/${encodeURIComponent(name)}/chain`, {
      params: new HttpParams().set('max_hops', maxHops),
    });
  }

  getCompanyTimeline(name: string): Observable<{ company: string; timeline: any[] }> {
    return this.http.get<any>(`${this.API}/api/v1/graph/company/${encodeURIComponent(name)}/timeline`);
  }

  getCompanyCompetitors(name: string): Observable<{ company: string; competitors: any[] }> {
    return this.http.get<any>(`${this.API}/api/v1/graph/company/${encodeURIComponent(name)}/competitors`);
  }

  // ── Analysis ──
  getEventImpact(eventName: string, maxHops = 3): Observable<ImpactResult> {
    return this.http.get<ImpactResult>(`${this.API}/api/v1/analysis/event/${encodeURIComponent(eventName)}/impact`, {
      params: new HttpParams().set('max_hops', maxHops),
    });
  }

  getCompanyExposure(name: string): Observable<any> {
    return this.http.get<any>(`${this.API}/api/v1/analysis/company/${encodeURIComponent(name)}/exposure`);
  }

  getCompanyReview(name: string): Observable<any> {
    return this.http.get<any>(`${this.API}/api/v1/analysis/company/${encodeURIComponent(name)}/review`);
  }

  getRecentEvents(days = 7, limit = 50): Observable<{ events: EventItem[]; total: number }> {
    return this.http.get<any>(`${this.API}/api/v1/analysis/events/recent`, {
      params: new HttpParams().set('days', days).set('limit', limit),
    });
  }

  listEvents(params?: { event_type?: string; entity_name?: string; limit?: number; offset?: number }): Observable<{ events: EventItem[]; total: number }> {
    let hp = new HttpParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') hp = hp.set(k, String(v));
      });
    }
    return this.http.get<any>(`${this.API}/api/v1/analysis/events`, { params: hp });
  }

  getDailyRuns(limit = 30): Observable<{ runs: DailyRun[]; total: number }> {
    return this.http.get<any>(`${this.API}/api/v1/analysis/daily-runs`, {
      params: new HttpParams().set('limit', limit),
    });
  }

  getImpactLogs(params?: { event_name?: string; limit?: number }): Observable<{ logs: any[]; total: number }> {
    let hp = new HttpParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') hp = hp.set(k, String(v));
      });
    }
    return this.http.get<any>(`${this.API}/api/v1/analysis/impact-logs`, { params: hp });
  }

  // ── Documents ──
  listDocuments(params?: { doc_type?: string; source_type?: string; status?: string; limit?: number }): Observable<{ documents: DocumentItem[]; total: number }> {
    let hp = new HttpParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') hp = hp.set(k, String(v));
      });
    }
    return this.http.get<any>(`${this.API}/api/v1/documents`, { params: hp });
  }

  uploadDocument(file: File, docType: string, company = ''): Observable<any> {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('doc_type', docType);
    if (company) fd.append('company_name', company);
    return this.http.post(`${this.API}/api/v1/documents/upload`, fd);
  }

  extractDocument(docId: string): Observable<any> {
    return this.http.post(`${this.API}/api/v1/documents/${docId}/extract`, {});
  }

  // ── Pipeline ──
  triggerDailyPipeline(): Observable<any> {
    return this.http.post(`${this.API}/api/v1/pipeline/daily`, {});
  }
}

