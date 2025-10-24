import {computed, Injectable, signal} from '@angular/core';
import {CronjobsApiService} from '../../../data-access/cronjobs/cronjobs-api.service';
import {Cronjob} from '../models/cronjob.model';

@Injectable({ providedIn: 'root' })
export class CronjobsStore {
  private readonly _items = signal<Cronjob[]>([]);
  private readonly _loading = signal(false);
  private readonly _error = signal<string | null>(null);

  readonly items = computed(() => this._items());
  readonly loading = computed(() => this._loading());
  readonly error = computed(() => this._error());

  constructor(private api: CronjobsApiService) {}

  loadAll(force = false) {
    if (this._items().length && !force) return;
    this._loading.set(true);
    this._error.set(null);
    this.api.list().subscribe({
      next: data => this._items.set(data),
      error: err => {
        console.error('[CronjobsStore] loadAll error', err);
        this._error.set('加载失败');
        this._loading.set(false);
      },
      complete: () => this._loading.set(false)
    });
  }
}

