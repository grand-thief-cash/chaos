import { Component, computed, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, FormControl, FormGroup } from '@angular/forms';
import { NzFormModule } from 'ng-zorro-antd/form';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzInputNumberModule } from 'ng-zorro-antd/input-number';

import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzMessageService } from 'ng-zorro-antd/message';
import { WorkbenchStore } from '../state/workbench.store';
import { WorkbenchRunRequest } from '../models/workbench.model';

@Component({
  selector: 'app-strategy-config',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    NzFormModule,
    NzSelectModule,
    NzInputModule,
    NzInputNumberModule,

    NzButtonModule,
    NzCardModule,
    NzDividerModule,
    NzAlertModule,
  ],
  template: `
    <nz-card>
      <div card-title style="display: flex; align-items: center; justify-content: space-between;">
        <span>Strategy Configuration</span>
        @if (store.sourceSelectorVisible()) {
          <div style="display: flex; align-items: center; gap: 8px;">
            @if (selectedSource !== 'relx') {
              <span style="color: #f5222d; font-size: 12px;">&bull; {{ sourceLabel(selectedSource) }}</span>
            }
            <nz-select
              [(ngModel)]="selectedSource"
              (ngModelChange)="onSourceChange($event)"
              nzSize="small"
              style="width: 130px;"
            >
              @for (s of store.sources(); track s) {
                <nz-option [nzLabel]="sourceLabel(s)" [nzValue]="s"></nz-option>
              }
            </nz-select>
          </div>
        }
      </div>

      @if (store.error()) {
        <nz-alert nzType="error" [nzMessage]="store.error()!" nzCloseable (nzOnClose)="store.clearResult()" style="margin-bottom: 16px;"></nz-alert>
      }

      <form nz-form [formGroup]="form" (ngSubmit)="onSubmit()">
        <nz-form-item>
          <nz-form-label [nzSpan]="6">Strategy</nz-form-label>
          <nz-form-control [nzSpan]="14">
            <nz-select formControlName="strategy_code" nzPlaceHolder="Select strategy" (ngModelChange)="onStrategyChange($event)">
              @for (s of store.strategies(); track s.code) {
                <nz-option [nzValue]="s.code" [nzLabel]="s.code"></nz-option>
              }
            </nz-select>
          </nz-form-control>
        </nz-form-item>

        @if (store.selectedStrategy(); as strategy) {
          <nz-divider nzText="Strategy Parameters"></nz-divider>
          @for (key of paramKeys(); track key) {
            <nz-form-item>
              <nz-form-label [nzSpan]="6">{{ paramDisplayLabel(key) }}</nz-form-label>
              <nz-form-control [nzSpan]="14">
                @if (paramSchema(key)?.type === 'enum') {
                  <nz-select [formControlName]="key" style="width: 100%;">
                    @for (opt of paramSchema(key)!.options; track opt) {
                      <nz-option [nzLabel]="opt" [nzValue]="opt"></nz-option>
                    }
                  </nz-select>
                } @else {
                  <nz-input-number
                    [formControlName]="key"
                    style="width: 100%;"
                  ></nz-input-number>
                }
              </nz-form-control>
            </nz-form-item>
          }
        }

        <nz-divider nzText="Data Dimensions"></nz-divider>
        <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px;">
          <nz-form-item style="margin-bottom: 0; flex: 1; min-width: 140px;">
            <nz-form-label [nzSpan]="8">Asset</nz-form-label>
            <nz-form-control [nzSpan]="14">
              <nz-select [(ngModel)]="selectedAssetType" (ngModelChange)="onAssetTypeChange($event)" [ngModelOptions]="{standalone: true}" nzSize="small">
                @for (a of store.assetTypes(); track a.value) {
                  <nz-option [nzLabel]="a.label" [nzValue]="a.value"></nz-option>
                }
              </nz-select>
            </nz-form-control>
          </nz-form-item>
          <nz-form-item style="margin-bottom: 0; flex: 1; min-width: 140px;">
            <nz-form-label [nzSpan]="8">Market</nz-form-label>
            <nz-form-control [nzSpan]="14">
              <nz-select [(ngModel)]="selectedMarket" [ngModelOptions]="{standalone: true}" nzSize="small">
                @for (m of store.markets(); track m.value) {
                  <nz-option [nzLabel]="m.label" [nzValue]="m.value"></nz-option>
                }
              </nz-select>
            </nz-form-control>
          </nz-form-item>
          <nz-form-item style="margin-bottom: 0; flex: 1; min-width: 140px;">
            <nz-form-label [nzSpan]="8">Period</nz-form-label>
            <nz-form-control [nzSpan]="14">
              <nz-select [(ngModel)]="selectedPeriod" [ngModelOptions]="{standalone: true}" nzSize="small">
                @for (p of store.periods(); track p.value) {
                  <nz-option [nzLabel]="p.label" [nzValue]="p.value"></nz-option>
                }
              </nz-select>
            </nz-form-control>
          </nz-form-item>
          @if (currentAdjustOptions().length > 0) {
            <nz-form-item style="margin-bottom: 0; flex: 1; min-width: 140px;">
              <nz-form-label [nzSpan]="8">Adjust</nz-form-label>
              <nz-form-control [nzSpan]="14">
                <nz-select [(ngModel)]="selectedAdjust" [ngModelOptions]="{standalone: true}" nzSize="small">
                  @for (a of currentAdjustOptions(); track a.value) {
                    <nz-option [nzLabel]="a.label" [nzValue]="a.value"></nz-option>
                  }
                </nz-select>
              </nz-form-control>
            </nz-form-item>
          }
        </div>

        <nz-divider nzText="Symbol &amp; Time"></nz-divider>
        <nz-form-item>
          <nz-form-label [nzSpan]="6">Symbol</nz-form-label>
          <nz-form-control [nzSpan]="14">
            <input nz-input formControlName="symbol" placeholder="e.g. 000001" />
          </nz-form-control>
        </nz-form-item>
        <nz-form-item>
          <nz-form-label [nzSpan]="6">Start Date</nz-form-label>
          <nz-form-control [nzSpan]="14">
            <input nz-input type="date" formControlName="start_date" style="width: 100%;" />
          </nz-form-control>
        </nz-form-item>
        <nz-form-item>
          <nz-form-label [nzSpan]="6">End Date</nz-form-label>
          <nz-form-control [nzSpan]="14">
            <input nz-input type="date" formControlName="end_date" style="width: 100%;" />
          </nz-form-control>
        </nz-form-item>

        <nz-divider nzText="Capital"></nz-divider>
        <nz-form-item>
          <nz-form-label [nzSpan]="6">Cash</nz-form-label>
          <nz-form-control [nzSpan]="14">
            <nz-input-number formControlName="cash" [nzMin]="0" [nzStep]="10000" style="width: 100%;"></nz-input-number>
          </nz-form-control>
        </nz-form-item>
        <nz-form-item>
          <nz-form-label [nzSpan]="6">Commission</nz-form-label>
          <nz-form-control [nzSpan]="14">
            <nz-input-number formControlName="commission" [nzMin]="0" [nzMax]="1" [nzStep]="0.0001" style="width: 100%;"></nz-input-number>
          </nz-form-control>
        </nz-form-item>

        <nz-form-item>
          <nz-form-control [nzSpan]="14" [nzOffset]="6">
            <button nz-button nzType="primary" [nzLoading]="store.running()" [disabled]="!form.valid || store.running()">
              Run Backtest
            </button>
          </nz-form-control>
        </nz-form-item>
      </form>
    </nz-card>
  `,
})
export class StrategyConfigComponent implements OnInit {
  store = inject(WorkbenchStore);
  private fb = inject(FormBuilder);
  private msg = inject(NzMessageService);

  paramKeys = computed(() => {
    const s = this.store.selectedStrategy();
    return s ? Object.keys(s.param_schema) : [];
  });

  paramSchema(key: string) {
    const s = this.store.selectedStrategy();
    return s?.param_schema[key] ?? null;
  }

  paramDisplayLabel(key: string): string {
    const schema = this.paramSchema(key);
    return schema?.display_name || key;
  }

  currentAdjustOptions = computed(() =>
    this.store.getAdjustOptionsForAsset(this.selectedAssetType),
  );

  form!: FormGroup;
  selectedSource = 'relx';
  selectedAssetType = '';
  selectedMarket = '';
  selectedPeriod = '';
  selectedAdjust = '';

  ngOnInit(): void {
    this.form = this.fb.group({
      strategy_code: [null],
      symbol: ['000001'],
      start_date: ['2024-01-01'],
      end_date: ['2024-12-31'],
      cash: [100000],
      commission: [0],
    });
    this.store.loadStrategies();
    this.store.loadSources(() => {
      this.selectedSource = this.store.selectedSource();
    });
    this.store.loadDataOptions(() => {
      this.initializeDimensionSelections();
    });
  }

  private initializeDimensionSelections(): void {
    const assetTypes = this.store.assetTypes();
    const markets = this.store.markets();
    const periods = this.store.periods();

    if (!assetTypes.some((item) => item.value === this.selectedAssetType)) {
      this.selectedAssetType = assetTypes[0]?.value ?? '';
    }
    if (!markets.some((item) => item.value === this.selectedMarket)) {
      this.selectedMarket = markets[0]?.value ?? '';
    }
    if (!periods.some((item) => item.value === this.selectedPeriod)) {
      this.selectedPeriod = periods[0]?.value ?? '';
    }

    const adjustOptions = this.store.getAdjustOptionsForAsset(this.selectedAssetType);
    if (!adjustOptions.some((item) => item.value === this.selectedAdjust)) {
      this.selectedAdjust = adjustOptions[0]?.value ?? '';
    }
  }

  sourceLabel(name: string): string {
    return name.charAt(0).toUpperCase() + name.slice(1);
  }

  onSourceChange(source: string): void {
    this.store.selectSource(source);
    this.msg.info('Source changed — run backtest again to use new data source');
  }

  onAssetTypeChange(assetType: string): void {
    const options = this.store.getAdjustOptionsForAsset(assetType);
    if (options.length > 0) {
      this.selectedAdjust = options[0].value;
    } else {
      this.selectedAdjust = '';
    }
  }

  onStrategyChange(code: string): void {
    this.store.selectStrategy(code);
    const strategy = this.store.selectedStrategy();
    if (!strategy) return;

    for (const key of Object.keys(this.form.controls)) {
      if (!['strategy_code', 'symbol', 'start_date', 'end_date', 'cash', 'commission'].includes(key)) {
        this.form.removeControl(key);
      }
    }

    for (const [key] of Object.entries(strategy.param_schema)) {
      this.form.addControl(key, new FormControl(strategy.default_params[key] ?? null));
    }
  }

  onSubmit(): void {
    if (this.form.invalid) return;
    if (!this.selectedAssetType || !this.selectedMarket || !this.selectedPeriod) {
      this.msg.warning('Data options are not ready yet');
      return;
    }
    const raw = this.form.value;

    const strategyParams: Record<string, any> = {};
    const fixedKeys = ['strategy_code', 'symbol', 'start_date', 'end_date', 'cash', 'commission'];
    for (const [key, value] of Object.entries(raw)) {
      if (!fixedKeys.includes(key)) {
        strategyParams[key] = value;
      }
    }

    const req: WorkbenchRunRequest = {
      strategy_code: raw.strategy_code,
      symbol: raw.symbol,
      start_date: this.formatDate(raw.start_date),
      end_date: this.formatDate(raw.end_date),
      period: this.selectedPeriod,
      adjust: this.selectedAdjust,
      asset_type: this.selectedAssetType,
      market: this.selectedMarket,
      cash: raw.cash,
      commission: raw.commission,
      strategy_params: strategyParams,
      source: this.store.sourceSelectorVisible() ? this.selectedSource : undefined,
    };
    this.store.runBacktest(req);
  }

  private formatDate(d: Date | null): string {
    if (!d) return '';
    const date = new Date(d);
    return date.toISOString().split('T')[0];
  }
}
