import {Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable, of} from 'rxjs';
import {delay} from 'rxjs/operators';
import {Cronjob} from '../../features/cronjobs/models/cronjob.model';

// 后续真实调用可使用 environment.baseApiUrl 拼接
// const API_BASE = '/api/cronjobs';

@Injectable({ providedIn: 'root' })
export class CronjobsApiService {
  constructor(private _http: HttpClient) {}

  list(): Observable<Cronjob[]> {
    const data = [
      { id: 'demo-1', name: 'Daily Sync', schedule: '0 0 * * *', status: 'active' } satisfies Cronjob
    ];
    return of<Cronjob[]>(data).pipe(delay(300));
    // return this.http.get<Cronjob[]>(API_BASE);
  }

  get(id: string): Observable<Cronjob> {
    const item = { id, name: 'Daily Sync', schedule: '0 0 * * *', status: 'active' } as Cronjob;
    return of<Cronjob>(item).pipe(delay(200));
    // return this.http.get<Cronjob>(`${API_BASE}/${id}`);
  }

  create(payload: Partial<Cronjob>): Observable<Cronjob> {
    const created: Cronjob = {
      id: 'new-id',
      name: payload.name || 'New',
      schedule: payload.schedule || '* * * * *',
      status: 'inactive'
    };
    return of(created).pipe(delay(200));
  }

  update(id: string, payload: Partial<Cronjob>): Observable<Cronjob> {
    const updated: Cronjob = {
      id,
      name: payload.name || 'Updated',
      schedule: payload.schedule || '* * * * *',
      status: (payload.status as Cronjob['status']) || 'active'
    };
    return of(updated).pipe(delay(200));
  }

  delete(_id: string): Observable<void> {
    return of<void>(undefined).pipe(delay(150));
  }
}
