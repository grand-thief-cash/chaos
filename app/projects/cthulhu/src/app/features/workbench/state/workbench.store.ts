import { computed, Injectable, signal } from '@angular/core';
import { WorkbenchApiService } from '../services/workbench-api.service';
import {
  WorkbenchStrategy,
  WorkbenchRunRequest,
  BacktestResult,
  DataOption,
  AdjustRule,
} from '../models/workbench.model';

const SOURCE_STORAGE_KEY = 'workbench-source';

@Injectable({ providedIn: 'root' })
export class WorkbenchStore {
  private readonly _strategies = signal<WorkbenchStrategy[]>([]);
  private readonly _selectedStrategy = signal<WorkbenchStrategy | null>(null);
  private readonly _result = signal<BacktestResult | null>(null);
  private readonly _loading = signal(false);
  private readonly _running = signal(false);
  private readonly _error = signal<string | null>(null);

  // ── Data source state ──
  private readonly _sources = signal<string[]>([]);
  private readonly _sourcesLoaded = signal(false);
  private readonly _selectedSource = signal<string>('default');

  // ── Data dimension options ──
  private readonly _assetTypes = signal<DataOption[]>([]);
  private readonly _markets = signal<DataOption[]>([]);
  private readonly _periods = signal<DataOption[]>([]);
  private readonly _adjustRules = signal<AdjustRule[]>([]);
  private readonly _dataOptionsLoaded = signal(false);

  readonly strategies = computed(() => this._strategies());
  readonly selectedStrategy = computed(() => this._selectedStrategy());
  readonly result = computed(() => this._result());
  readonly loading = computed(() => this._loading());
  readonly running = computed(() => this._running());
  readonly error = computed(() => this._error());

  readonly sources = computed(() => this._sources());
  readonly sourcesLoaded = computed(() => this._sourcesLoaded());
  readonly selectedSource = computed(() => this._selectedSource());
  readonly sourceSelectorVisible = computed(() => this._sources().length > 1);

  readonly assetTypes = computed(() => this._assetTypes());
  readonly markets = computed(() => this._markets());
  readonly periods = computed(() => this._periods());
  readonly adjustRules = computed(() => this._adjustRules());
  readonly dataOptionsLoaded = computed(() => this._dataOptionsLoaded());

  constructor(private api: WorkbenchApiService) {
    // restore source from localStorage
    const cached = localStorage.getItem(SOURCE_STORAGE_KEY);
    if (cached) {
      this._selectedSource.set(cached);
    }
  }

  loadSources(): void {
    if (this._sourcesLoaded()) return;
    this.api.getSources().subscribe({
      next: (resp) => {
        this._sources.set(resp.sources);
        this._sourcesLoaded.set(true);
        // if cached source is not in the list, fall back to default
        const current = this._selectedSource();
        if (!resp.sources.includes(current)) {
          this._selectedSource.set(resp.default);
          localStorage.setItem(SOURCE_STORAGE_KEY, resp.default);
        }
      },
      error: () => {
        // fallback: only default available
        this._sources.set(['default']);
        this._sourcesLoaded.set(true);
      },
    });
  }

  selectSource(source: string): void {
    this._selectedSource.set(source);
    localStorage.setItem(SOURCE_STORAGE_KEY, source);
    // clear any loaded result when source changes
    this._result.set(null);
    this._error.set(null);
  }

  loadDataOptions(): void {
    if (this._dataOptionsLoaded()) return;
    this.api.getDataOptions().subscribe({
      next: (resp) => {
        this._assetTypes.set(resp.asset_types);
        this._markets.set(resp.markets);
        this._periods.set(resp.periods);
        this._adjustRules.set(resp.adjust_rules);
        this._dataOptionsLoaded.set(true);
      },
      error: () => {
        this._dataOptionsLoaded.set(true);
      },
    });
  }

  getAdjustOptionsForAsset(assetType: string): DataOption[] {
    const rule = this._adjustRules().find(r => r.asset_type === assetType);
    return rule?.options ?? [];
  }

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
