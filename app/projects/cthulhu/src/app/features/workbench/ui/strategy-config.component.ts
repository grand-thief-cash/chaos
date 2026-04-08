import { Component, inject, OnInit, computed } from '@angular/core';
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
            @if (selectedSource !== 'default') {
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
              <nz-form-label [nzSpan]="6">{{ key }}</nz-form-label>
              <nz-form-control [nzSpan]="14">
                <nz-input-number
                  [formControlName]="key"
                  style="width: 100%;"
                ></nz-input-number>
              </nz-form-control>
            </nz-form-item>
          }
        }

        <nz-divider nzText="Data &amp; Time"></nz-divider>
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

  form!: FormGroup;
  selectedSource = 'default';

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
    this.store.loadSources();
    this.selectedSource = this.store.selectedSource();
  }

  sourceLabel(name: string): string {
    return name.charAt(0).toUpperCase() + name.slice(1);
  }

  onSourceChange(source: string): void {
    this.store.selectSource(source);
    this.msg.info('Source changed — run backtest again to use new data source');
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
      timeframe: 'daily',
      adjust: 'nf',
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
