import {Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {Task, TaskRun} from '../../features/cronjobs/models/cronjob.model';
import {environment} from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class CronjobsApiService {
  private API_BASE = environment.cronjobApiBase;
  constructor(private _http: HttpClient) {}

  listTasks(): Observable<Task[]> {
    return this._http.get<Task[]>(`${this.API_BASE}/tasks`);
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
    return this._http.get<TaskRun[]>(`${this.API_BASE}/tasks/${taskId}/runs`);
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
}
