import {computed, Injectable, signal} from '@angular/core';
import {CronjobsApiService} from '../../../data-access/cronjobs/cronjobs-api.service';
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

  readonly tasks = computed(() => this._tasks());
  readonly taskPageIndex = computed(() => this._taskPageIndex());
  readonly taskPageSize = computed(() => this._taskPageSize());
  readonly taskSearch = computed(()=> this._taskSearch());
  readonly taskStatusFilter = computed(()=> this._taskStatusFilter());
  filteredTasks = computed(()=> {
    const s = this._taskSearch().trim().toLowerCase();
    const f = this._taskStatusFilter();
    return this._tasks().filter(t => {
      if (s && !t.name.toLowerCase().includes(s)) return false;
      if (f !== 'ALL' && t.status !== f) return false;
      return true;
    });
  });
  pagedTasks = computed(() => {
    const list = this.filteredTasks();
    const page = this._taskPageIndex();
    const size = this._taskPageSize();
    const start = (page - 1) * size;
    return list.slice(start, start + size);
  });
  readonly error = computed(() => this._error());
  readonly loadingTasks = computed(() => this._loadingTasks());
  runsFor(taskId: number) { return computed(() => this._runs()[taskId] || []); }
  loadingRunsFor(taskId: number) { return computed(() => this._loadingRuns()[taskId] || false); }
  runPage(taskId: number){ return computed(()=> this._runPageIndex()[taskId] || 1); }
  runPageSize(taskId: number){ return computed(()=> this._runPageSize()[taskId] || 10); }

  constructor(private api: CronjobsApiService) {}

  loadTasks(force = false) {
    if (this._tasks().length && !force) return;
    this._loadingTasks.set(true);
    this._error.set(null);
    this.api.listTasks().subscribe({
      next: data => this._tasks.set(data),
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

  setTaskPage(index: number){ this._taskPageIndex.set(index); }
  setTaskPageSize(size: number){ this._taskPageSize.set(size); this._taskPageIndex.set(1); }
  setTaskSearch(v: string){ this._taskSearch.set(v); this._taskPageIndex.set(1); }
  setTaskStatusFilter(v: 'ALL' | 'ENABLED' | 'DISABLED'){ this._taskStatusFilter.set(v); this._taskPageIndex.set(1); }
  setRunPage(taskId: number, page: number){ this._runPageIndex.set({ ...this._runPageIndex(), [taskId]: page }); }
  setRunPageSize(taskId: number, size: number){ this._runPageSize.set({ ...this._runPageSize(), [taskId]: size }); this.setRunPage(taskId, 1); }
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
}
