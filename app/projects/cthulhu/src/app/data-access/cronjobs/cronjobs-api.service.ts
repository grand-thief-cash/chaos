import {Injectable} from '@angular/core';
import {HttpClient, HttpParams} from '@angular/common/http';
import {map, Observable} from 'rxjs';
import {Task, TaskRun} from '../../features/cronjobs/models/cronjob.model';
import {environment} from '../../../environments/environment';

export interface TaskListResponse { items: Task[]; total: number; limit: number; offset: number; }
export interface TaskListQuery {
  status?: 'ENABLED' | 'DISABLED';
  name?: string;
  description?: string;
  created_from?: string; // RFC3339
  created_to?: string;
  updated_from?: string;
  updated_to?: string;
  limit?: number;
  offset?: number;
}

@Injectable({ providedIn: 'root' })
export class CronjobsApiService {
  private API_BASE = environment.cronjobApiBase;
  constructor(private _http: HttpClient) {}

  listTasks(q: TaskListQuery = {}): Observable<TaskListResponse> {
    let params = new HttpParams();
    Object.entries(q).forEach(([k,v])=> {
      if (v === undefined || v === null || v === '') return;
      params = params.set(k, String(v));
    });
    return this._http.get<any>(`${this.API_BASE}/tasks`, { params }).pipe(
      map(resp => {
        console.debug('[CronjobsApiService] listTasks raw resp', resp);
        if (Array.isArray(resp)) {
          return { items: resp as Task[], total: resp.length, limit: q.limit || resp.length, offset: q.offset || 0 };
        }
        // fallback keys: data, list
        const items = resp?.items || resp?.data || resp?.list || [];
        const total = resp?.total ?? (Array.isArray(items)? items.length: 0);
        return { items, total, limit: resp?.limit ?? q.limit ?? items.length, offset: resp?.offset ?? q.offset ?? 0 } as TaskListResponse;
      })
    );
  }
  getTask(id: number): Observable<Task> {
    return this._http.get<Task>(`${this.API_BASE}/tasks/${id}`);
  }
  createTask(payload: Partial<Task>): Observable<{ id: number; name: string }> {
    return this._http.post<{ id: number; name: string }>(`${this.API_BASE}/tasks`, payload);
  }
  updateTask(id: number, payload: Partial<Task>): Observable<{ updated: boolean }> {
    return this._http.put<{ updated: boolean }>(`${this.API_BASE}/tasks/${id}`, payload);
  }
  deleteTask(id: number): Observable<{ deleted: boolean }> {
    return this._http.delete<{ deleted: boolean }>(`${this.API_BASE}/tasks/${id}`);
  }
  enableTask(id: number): Observable<{ updated: boolean }> {
    return this._http.patch<{ updated: boolean }>(`${this.API_BASE}/tasks/${id}/enable`, {});
  }
  disableTask(id: number): Observable<{ updated: boolean }> {
    return this._http.patch<{ updated: boolean }>(`${this.API_BASE}/tasks/${id}/disable`, {});
  }
  triggerTask(id: number): Observable<{ run_id: number }> {
    return this._http.post<{ run_id: number }>(`${this.API_BASE}/tasks/${id}/trigger`, {});
  }
  listRuns(taskId: number): Observable<TaskRun[]> {
    return this._http.get<any>(`${this.API_BASE}/tasks/${taskId}/runs`).pipe(
      map(resp => {
        console.debug('[CronjobsApiService] listRuns raw resp', resp);
        if (Array.isArray(resp)) return resp as TaskRun[];
        return (resp?.items || resp?.data || resp?.list || []) as TaskRun[];
      })
    );
  }
  getRun(runId: number): Observable<TaskRun> {
    return this._http.get<TaskRun>(`${this.API_BASE}/runs/${runId}`);
  }
  cancelRun(runId: number): Observable<{ canceled: boolean }> {
    return this._http.post<{ canceled: boolean }>(`${this.API_BASE}/runs/${runId}/cancel`, {});
  }
  refreshCache(): Observable<{ refreshed: boolean }> {
    return this._http.post<{ refreshed: boolean }>(`${this.API_BASE}/tasks/cache/refresh`, {});
  }
  listRunsFiltered(taskId: number, q: { status?: string; from?: string; to?: string; limit?: number; offset?: number; time_field?: string } = {}) {
    let params = new HttpParams();
    Object.entries(q).forEach(([k,v])=> { if(v!==undefined && v!==null && v!==''){ params = params.set(k, String(v)); } });
    return this._http.get<any>(`${this.API_BASE}/tasks/${taskId}/runs`, { params });
  }
  taskRunStats(taskId: number){
    return this._http.get<any>(`${this.API_BASE}/tasks/${taskId}/runs/stats`);
  }
  listActiveRuns(q: { status?: string; from?: string; to?: string; limit?: number; offset?: number; time_field?: string } = {}){
    let params = new HttpParams();
    Object.entries(q).forEach(([k,v])=> { if(v!==undefined && v!==null && v!==''){ params = params.set(k, String(v)); } });
    return this._http.get<any>(`${this.API_BASE}/runs/active`, { params }).pipe(
      map(resp => {
        console.debug('[CronjobsApiService] listActiveRuns raw resp', resp);
        return Array.isArray(resp) ? resp : (resp?.items || []);
      })
    );
  }
  runsSummary(){
    return this._http.get<any>(`${this.API_BASE}/runs/summary`);
  }
  runProgress(runId: number){ return this._http.get<any>(`${this.API_BASE}/runs/${runId}/progress`); }
  setRunProgress(runId: number, payload: { current?: number; total?: number; message?: string }){ return this._http.post<any>(`${this.API_BASE}/runs/${runId}/progress`, payload); }
  finalizeCallback(runId: number, payload: { result: string; code?: number; body?: string; error_message?: string }){ return this._http.post<any>(`${this.API_BASE}/runs/${runId}/callback`, payload); }
  cleanupRuns(payload: any){ return this._http.post<any>(`${this.API_BASE}/runs/cleanup`, payload); }
  listAllRunProgress(){
    return this._http.get<any>(`${this.API_BASE}/runs/progress`).pipe(
      map(resp => resp?.items || [])
    );
  }
}
