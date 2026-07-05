import { computed, Injectable, signal } from '@angular/core';
import { WorkbenchApiService } from '../services/workbench-api.service';
import {
  DataOption,
  AdjustRule,
} from '../models/workbench.model';

const SOURCE_STORAGE_KEY = 'workbench-source';

@Injectable({ providedIn: 'root' })
export class WorkbenchStore {
  // ── Data source state ──
  private readonly _sources = signal<string[]>([]);
  private readonly _sourcesLoaded = signal(false);
  private readonly _selectedSource = signal<string>('relx');

  // ── Data dimension options ──
  private readonly _assetTypes = signal<DataOption[]>([]);
  private readonly _markets = signal<DataOption[]>([]);
  private readonly _periods = signal<DataOption[]>([]);
  private readonly _adjustRules = signal<AdjustRule[]>([]);
  private readonly _dataOptionsLoaded = signal(false);

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

  loadSources(onLoaded?: () => void): void {
    if (this._sourcesLoaded()) {
      onLoaded?.();
      return;
    }
    this.api.getSources().subscribe({
      next: (resp) => {
        this._sources.set(resp.sources);
        this._sourcesLoaded.set(true);
        // if cached source is not in the list, fall back to current
        const current = this._selectedSource();
        if (!resp.sources.includes(current)) {
          this._selectedSource.set(resp.current);
          localStorage.setItem(SOURCE_STORAGE_KEY, resp.current);
        }
        onLoaded?.();
      },
      error: () => {
        // fallback: only current local source available
        this._sources.set(['relx']);
        this._selectedSource.set('relx');
        this._sourcesLoaded.set(true);
        onLoaded?.();
      },
    });
  }

  selectSource(source: string): void {
    this._selectedSource.set(source);
    localStorage.setItem(SOURCE_STORAGE_KEY, source);
  }

  loadDataOptions(onLoaded?: () => void): void {
    if (this._dataOptionsLoaded()) {
      onLoaded?.();
      return;
    }
    this.api.getDataOptions().subscribe({
      next: (resp) => {
        this._assetTypes.set(resp.asset_types);
        this._markets.set(resp.markets);
        this._periods.set(resp.periods);
        this._adjustRules.set(resp.adjust_rules);
        this._dataOptionsLoaded.set(true);
        onLoaded?.();
      },
      error: () => {
        this._dataOptionsLoaded.set(true);
        onLoaded?.();
      },
    });
  }

  getAdjustOptionsForAsset(assetType: string): DataOption[] {
    const rule = this._adjustRules().find(r => r.asset_type === assetType);
    return rule?.options ?? [];
  }
}
