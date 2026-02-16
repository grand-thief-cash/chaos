import {inject, Injectable} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {Observable} from 'rxjs';
import {
  ArtemisTask,
  TaskUnitFile,
  TaskUnitRegisterReq,
  TaskUnitsTree,
  TaskYaml,
  UnregisteredTask
} from '../models/artemis.models';
import {environment} from '../../../../environments/environment';

const BASE_URL = environment.artemisApiBase;

@Injectable({
  providedIn: 'root'
})
export class ArtemisService {
  private http = inject(HttpClient);

  getTasks(): Observable<{ tasks: ArtemisTask[] }> {
    return this.http.get<{ tasks: ArtemisTask[] }>(`${BASE_URL}/tasks`);
  }

  getTaskYaml(): Observable<TaskYaml> {
    return this.http.get<TaskYaml>(`${BASE_URL}/runtime/task-yaml`);
  }

  updateTaskYaml(content: string): Observable<TaskYaml> {
    return this.http.put<TaskYaml>(`${BASE_URL}/runtime/task-yaml`, { content });
  }

  getTaskUnitsTree(): Observable<TaskUnitsTree> {
    return this.http.get<TaskUnitsTree>(`${BASE_URL}/runtime/task-units/tree`);
  }

  getTaskUnitFile(path: string): Observable<TaskUnitFile> {
    return this.http.get<TaskUnitFile>(`${BASE_URL}/runtime/task-units/file`, { params: { path } });
  }

  updateTaskUnitFile(path: string, content: string): Observable<TaskUnitFile> {
    return this.http.put<TaskUnitFile>(`${BASE_URL}/runtime/task-units/file`, { path, content });
  }

  createTaskUnitFile(path: string, content: string): Observable<TaskUnitFile> {
    return this.http.post<TaskUnitFile>(`${BASE_URL}/runtime/task-units/file`, { path, content });
  }

  registerTaskUnit(req: TaskUnitRegisterReq): Observable<any> {
    return this.http.post(`${BASE_URL}/runtime/task-units/register`, req);
  }

  getUnregisteredTasks(): Observable<{ tasks: UnregisteredTask[] }> {
    return this.http.get<{ tasks: UnregisteredTask[] }>(`${BASE_URL}/tasks/unregistered`);
  }

  unregisterTask(taskCode: string): Observable<any> {
    return this.http.post(`${BASE_URL}/tasks/unregister/${taskCode}`, {});
  }

  renameTaskUnit(oldPath: string, newPath: string): Observable<any> {
    return this.http.post(`${BASE_URL}/runtime/task-units/rename`, { old_path: oldPath, new_path: newPath });
  }

  deleteTaskUnit(path: string): Observable<any> {
    return this.http.delete(`${BASE_URL}/runtime/task-units/file`, { params: { path } });
  }
}
