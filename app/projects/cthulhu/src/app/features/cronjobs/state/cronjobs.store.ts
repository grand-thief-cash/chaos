import {computed, Injectable, signal} from '@angular/core';
import {CronjobsApiService, TaskListQuery, TaskListResponse} from '../../../data-access/cronjobs/cronjobs-api.service';
import {Task, TaskRun} from '../models/cronjob.model';

@Injectable({ providedIn: 'root' })
export class CronjobsStore {
  private readonly _tasks = signal<Task[]>([]);
  // pagination signals
  private readonly _taskPageIndex = signal(1);
  private readonly _taskPageSize = signal(10);
  private readonly _runs = signal<Record<number, TaskRun[]>>({}); // keyed by task_id
  private readonly _loadingTasks = signal(false);
  private readonly _loadingRuns = signal<Record<number, boolean>>({});
  private readonly _error = signal<string | null>(null);
  private readonly _taskSearch = signal('');
  private readonly _taskStatusFilter = signal<'ALL' | 'ENABLED' | 'DISABLED'>('ALL');
  private readonly _runPageIndex = signal<Record<number, number>>({});
  private readonly _runPageSize = signal<Record<number, number>>({});
  private readonly _taskDescriptionSearch = signal('');
  private readonly _createdRange = signal<{from?: string; to?: string}>({});
  private readonly _updatedRange = signal<{from?: string; to?: string}>({});
  private readonly _taskTotal = signal(0);

  readonly tasks = computed(() => this._tasks());
  readonly taskPageIndex = computed(() => this._taskPageIndex());
  readonly taskPageSize = computed(() => this._taskPageSize());
  readonly taskTotal = computed(()=> this._taskTotal());
  // method for template boolean check
  loadingTasks(){ return this._loadingTasks(); }

  // server side list (no longer filter locally except fallback)
  filteredTasks = computed(()=> this._tasks());
  pagedTasks = computed(()=> this.filteredTasks());

  constructor(private api: CronjobsApiService) {}

  loadTasks(_force = true) {
    this._loadingTasks.set(true);
    const q: TaskListQuery = {
      limit: this._taskPageSize(),
      offset: (this._taskPageIndex()-1) * this._taskPageSize(),
    };
    const name = this._taskSearch().trim();
    if (name) q.name = name;
    const status = this._taskStatusFilter();
    if (status !== 'ALL') q.status = status;
    const desc = this._taskDescriptionSearch().trim();
    if (desc) q.description = desc;
    const cr = this._createdRange();
    if (cr.from) q.created_from = cr.from;
    if (cr.to) q.created_to = cr.to;
    const ur = this._updatedRange();
    if (ur.from) q.updated_from = ur.from;
    if (ur.to) q.updated_to = ur.to;
    this.api.listTasks(q).subscribe({
      next: (resp: TaskListResponse) => { this._tasks.set(resp.items); this._taskTotal.set(resp.total); },
      error: err => { console.error('[CronjobsStore] loadTasks error', err); this._error.set('加载任务失败'); this._loadingTasks.set(false); },
      complete: () => this._loadingTasks.set(false)
    });
  }

  loadRuns(taskId: number, force = false) {
    const existing = this._runs()[taskId];
    if (existing && existing.length && !force) return;
    this._loadingRuns.set({ ...this._loadingRuns(), [taskId]: true });
    this.api.listRuns(taskId).subscribe({
      next: data => this._runs.set({ ...this._runs(), [taskId]: data }),
      error: err => { console.error('[CronjobsStore] loadRuns error', err); this._error.set('加载运行记录失败'); this._loadingRuns.set({ ...this._loadingRuns(), [taskId]: false }); },
      complete: () => this._loadingRuns.set({ ...this._loadingRuns(), [taskId]: false })
    });
  }

  setTaskPage(index: number){ this._taskPageIndex.set(index); this.loadTasks(true); }
  setTaskPageSize(size: number){ this._taskPageSize.set(size); this._taskPageIndex.set(1); this.loadTasks(true); }
  setTaskSearch(v: string){ this._taskSearch.set(v); this._taskPageIndex.set(1); this.loadTasks(true); }
  setTaskDescriptionSearch(v: string){ this._taskDescriptionSearch.set(v); this._taskPageIndex.set(1); this.loadTasks(true); }
  setTaskStatusFilter(v: 'ALL' | 'ENABLED' | 'DISABLED'){ this._taskStatusFilter.set(v); this._taskPageIndex.set(1); this.loadTasks(true); }
  setCreatedRange(from?: string, to?: string){ this._createdRange.set({from,to}); this._taskPageIndex.set(1); this.loadTasks(true); }
  setUpdatedRange(from?: string, to?: string){ this._updatedRange.set({from,to}); this._taskPageIndex.set(1); this.loadTasks(true); }
  setRunPage(taskId: number, page: number){
    this._runPageIndex.set({ ...this._runPageIndex(), [taskId]: page });
  }
  setRunPageSize(taskId: number, size: number){
    this._runPageSize.set({ ...this._runPageSize(), [taskId]: size });
    this.setRunPage(taskId, 1);
  }
  runsFor(taskId: number) { return computed(() => this._runs()[taskId] || []); }
  loadingRunsFor(taskId: number) { return computed(() => this._loadingRuns()[taskId] || false); }
  runPage(taskId: number){ return computed(()=> this._runPageIndex()[taskId] || 1); }
  runPageSize(taskId: number){ return computed(()=> this._runPageSize()[taskId] || 10); }
  pagedRuns(taskId: number){ return computed(()=> {
    const runs = this._runs()[taskId] || [];
    const page = this.runPage(taskId)();
    const size = this.runPageSize(taskId)();
    const start = (page - 1) * size;
    return runs.slice(start, start + size);
  }); }

  enable(id: number) { return this.api.enableTask(id); }
  disable(id: number) { return this.api.disableTask(id); }
  trigger(id: number) { return this.api.triggerTask(id); }
  refreshCache() { return this.api.refreshCache(); }
  delete(id: number){ return this.api.deleteTask(id); }

  applyFilters(f: { name?: string; desc?: string; status?: 'ALL'|'ENABLED'|'DISABLED'; createdFrom?: string; createdTo?: string; updatedFrom?: string; updatedTo?: string; }) {
    this._taskSearch.set(f.name?.trim() || '');
    this._taskDescriptionSearch.set(f.desc?.trim() || '');
    this._taskStatusFilter.set(f.status || 'ALL');
    this._createdRange.set({ from: f.createdFrom, to: f.createdTo });
    this._updatedRange.set({ from: f.updatedFrom, to: f.updatedTo });
    this._taskPageIndex.set(1);
    this.loadTasks(true);
  }
  resetFilters(){
    this.applyFilters({});
  }
}
