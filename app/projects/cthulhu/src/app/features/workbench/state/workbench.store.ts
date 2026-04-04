import { computed, Injectable, signal } from '@angular/core';
import { WorkbenchApiService } from '../services/workbench-api.service';
import {
  WorkbenchStrategy,
  WorkbenchRunRequest,
  BacktestResult,
} from '../models/workbench.model';

@Injectable({ providedIn: 'root' })
export class WorkbenchStore {
  private readonly _strategies = signal<WorkbenchStrategy[]>([]);
  private readonly _selectedStrategy = signal<WorkbenchStrategy | null>(null);
  private readonly _result = signal<BacktestResult | null>(null);
  private readonly _loading = signal(false);
  private readonly _running = signal(false);
  private readonly _error = signal<string | null>(null);

  readonly strategies = computed(() => this._strategies());
  readonly selectedStrategy = computed(() => this._selectedStrategy());
  readonly result = computed(() => this._result());
  readonly loading = computed(() => this._loading());
  readonly running = computed(() => this._running());
  readonly error = computed(() => this._error());

  constructor(private api: WorkbenchApiService) {}

  loadStrategies(): void {
    this._loading.set(true);
    this.api.getStrategies().subscribe({
      next: (resp) => {
        this._strategies.set(resp.strategies);
        this._loading.set(false);
      },
      error: () => {
        this._error.set('Failed to load strategies');
        this._loading.set(false);
      },
    });
  }

  selectStrategy(code: string): void {
    const strategy = this._strategies().find((s) => s.code === code) ?? null;
    this._selectedStrategy.set(strategy);
    this._result.set(null);
    this._error.set(null);
  }

  runBacktest(req: WorkbenchRunRequest): void {
    this._running.set(true);
    this._error.set(null);
    this.api.runBacktest(req).subscribe({
      next: (result) => {
        this._result.set(result);
        this._running.set(false);
      },
      error: (err) => {
        this._error.set(err.error?.detail ?? err.message ?? 'Backtest failed');
        this._running.set(false);
      },
    });
  }

  clearResult(): void {
    this._result.set(null);
    this._error.set(null);
  }
}
