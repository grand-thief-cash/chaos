import {Component, inject, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {NzCardModule} from 'ng-zorro-antd/card';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzInputModule} from 'ng-zorro-antd/input';
import {NzTabsModule} from 'ng-zorro-antd/tabs';
import {NzTagModule} from 'ng-zorro-antd/tag';
import {NzSpinModule} from 'ng-zorro-antd/spin';
import {NzDividerModule} from 'ng-zorro-antd/divider';
import {NzEmptyModule} from 'ng-zorro-antd/empty';
import {NzToolTipModule} from 'ng-zorro-antd/tooltip';
import {NzIconModule} from 'ng-zorro-antd/icon';
import {NzDescriptionsModule} from 'ng-zorro-antd/descriptions';
import {NzProgressModule} from 'ng-zorro-antd/progress';
import {NzStatisticModule} from 'ng-zorro-antd/statistic';
import {NzGridModule} from 'ng-zorro-antd/grid';
import {NzSelectModule} from 'ng-zorro-antd/select';
import {NzInputNumberModule} from 'ng-zorro-antd/input-number';
import {NzMessageService} from 'ng-zorro-antd/message';
import {NzAlertModule} from 'ng-zorro-antd/alert';
import {NzBadgeModule} from 'ng-zorro-antd/badge';

import {RegimeService} from '../services/regime.service';
import {RegimeFeatures, RegimeResult} from '../models/regime.models';

@Component({
  selector: 'app-regime-engine',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    NzCardModule, NzTableModule, NzButtonModule, NzInputModule,
    NzTabsModule, NzTagModule, NzSpinModule, NzDividerModule,
    NzEmptyModule, NzToolTipModule, NzIconModule, NzDescriptionsModule,
    NzProgressModule, NzStatisticModule, NzGridModule, NzSelectModule,
    NzInputNumberModule, NzAlertModule, NzBadgeModule
  ],
  template: `
    <nz-tabset>
      <!-- ==================== Tab 1: Current Regime ==================== -->
      <nz-tab nzTitle="Current Regime">
        <div class="action-bar">
          <button nz-button nzType="default" (click)="loadCurrent()" [nzLoading]="loadingCurrent">
            <span nz-icon nzType="reload"></span> Refresh
          </button>
        </div>

        <div *ngIf="current; else noRegime">
          <!-- Market Label Banner -->
          <nz-alert
            [nzType]="labelAlertType(current.label_market)"
            [nzMessage]="regimeBanner"
            nzShowIcon
            style="margin-bottom: 16px;">
          </nz-alert>
          <ng-template #regimeBanner>
            <strong>{{ current.label_market || 'UNKNOWN' }}</strong>
            &nbsp;|&nbsp; Vol: <nz-tag [nzColor]="volTagColor(current.label_vol)">{{ current.label_vol || '-' }}</nz-tag>
            &nbsp;|&nbsp; Confidence: {{ current.label_confidence || '-' }}
            &nbsp;|&nbsp; Date: {{ current.trade_date }}
          </ng-template>

          <!-- State Dimensions -->
          <nz-card nzTitle="State Dimensions" [nzBordered]="false" style="margin-bottom: 16px;">
            <div nz-row [nzGutter]="[16, 16]">
              <div nz-col [nzSpan]="8" *ngFor="let dim of stateDimensions">
                <div class="dim-card">
                  <div class="dim-label">{{ dim.label }}</div>
                  <nz-progress
                    [nzPercent]="dim.value * 100"
                    [nzStrokeColor]="dimColor(dim.value, dim.invert)"
                    [nzShowInfo]="true"
                    [nzFormat]="dimFormatter(dim.value)"
                    nzSize="small">
                  </nz-progress>
                  <div class="dim-desc">{{ dim.desc }}</div>
                </div>
              </div>
            </div>
          </nz-card>

          <!-- Transition Signals -->
          <nz-card nzTitle="Transition Signals" [nzBordered]="false" style="margin-bottom: 16px;">
            <div nz-row [nzGutter]="16">
              <div nz-col [nzSpan]="12">
                <nz-descriptions nzBordered nzSize="small" [nzColumn]="1">
                  <nz-descriptions-item nzTitle="Breadth Momentum">
                    <span [style.color]="signalColor(current.breadth_momentum)">
                      {{ current.breadth_momentum | number:'1.3-3' }}
                      {{ current.breadth_momentum > 0 ? '▲' : current.breadth_momentum < 0 ? '▼' : '—' }}
                    </span>
                  </nz-descriptions-item>
                  <nz-descriptions-item nzTitle="Vol Acceleration">
                    <span [style.color]="signalColor(current.vol_acceleration)">
                      {{ current.vol_acceleration | number:'1.3-3' }}
                      {{ current.vol_acceleration > 0 ? '▲' : current.vol_acceleration < 0 ? '▼' : '—' }}
                    </span>
                  </nz-descriptions-item>
                </nz-descriptions>
              </div>
            </div>
          </nz-card>

          <!-- Strategy Allocation -->
          <nz-card nzTitle="Strategy Allocation" [nzBordered]="false" *ngIf="current.strategy_weights">
            <div nz-row [nzGutter]="16">
              <div nz-col [nzSpan]="12">
                <nz-descriptions nzBordered nzSize="small" [nzColumn]="1">
                  <nz-descriptions-item nzTitle="Position Limit">
                    {{ (current.position_limit || 0) * 100 | number:'1.0-0' }}%
                  </nz-descriptions-item>
                  <nz-descriptions-item nzTitle="Holding Period">
                    <nz-tag nzColor="blue">{{ current.suggested_holding_period || '-' }}</nz-tag>
                  </nz-descriptions-item>
                </nz-descriptions>
              </div>
            </div>
            <nz-divider nzText="Strategy Weights" nzOrientation="left"></nz-divider>
            <nz-table #weightTable [nzData]="strategyWeightEntries" nzSize="small" [nzShowPagination]="false" [nzBordered]="true">
              <thead><tr><th>Strategy</th><th>Weight</th></tr></thead>
              <tbody>
                <tr *ngFor="let e of weightTable.data">
                  <td>{{ e[0] }}</td>
                  <td style="font-family: monospace;">{{ e[1] | number:'1.2-2' }}</td>
                </tr>
              </tbody>
            </nz-table>
            <nz-divider nzText="Factor Weight Adjustments" nzOrientation="left" *ngIf="factorAdjEntries.length"></nz-divider>
            <nz-table *ngIf="factorAdjEntries.length" #adjTable [nzData]="factorAdjEntries" nzSize="small" [nzShowPagination]="false" [nzBordered]="true">
              <thead><tr><th>Factor</th><th>Adjustment</th></tr></thead>
              <tbody>
                <tr *ngFor="let e of adjTable.data">
                  <td>{{ e[0] }}</td>
                  <td style="font-family: monospace;" [style.color]="e[1] >= 0 ? '#52c41a' : '#ff4d4f'">
                    {{ e[1] > 0 ? '+' : '' }}{{ e[1] | number:'1.3-3' }}
                  </td>
                </tr>
              </tbody>
            </nz-table>
          </nz-card>
        </div>
        <ng-template #noRegime>
          <nz-empty *ngIf="!loadingCurrent" nzNotFoundContent="No regime computed yet. Use the Compute tab to run."></nz-empty>
        </ng-template>
      </nz-tab>

      <!-- ==================== Tab 2: History ==================== -->
      <nz-tab nzTitle="History" (nzClick)="loadHistory()">
        <nz-card [nzBordered]="false">
          <div class="action-bar">
            <label class="field-label" style="display: inline-block; margin-right: 8px;">Limit</label>
            <nz-input-number [(ngModel)]="historyLimit" [nzMin]="1" [nzMax]="500" [nzStep]="10" style="width: 80px; margin-right: 12px;"></nz-input-number>
            <button nz-button nzType="default" (click)="loadHistory()" [nzLoading]="loadingHistory">
              <span nz-icon nzType="reload"></span> Refresh
            </button>
          </div>
          <nz-table #histTable [nzData]="history" [nzLoading]="loadingHistory" nzSize="small" [nzPageSize]="20"
                    [nzScroll]="{ x: '1200px' }">
            <thead>
              <tr>
                <th nzWidth="100px" nzLeft>Date</th>
                <th nzWidth="80px">Market</th>
                <th nzWidth="60px">Vol</th>
                <th nzWidth="70px" nz-tooltip="Trend Strength">Trend</th>
                <th nzWidth="70px" nz-tooltip="Risk Appetite">Risk</th>
                <th nzWidth="70px" nz-tooltip="Volatility Stress">VolStrs</th>
                <th nzWidth="70px" nz-tooltip="Market Breadth">Breadth</th>
                <th nzWidth="70px" nz-tooltip="Liquidity">Liq</th>
                <th nzWidth="70px" nz-tooltip="Sector Concentration">Conc</th>
                <th nzWidth="70px" nz-tooltip="Breadth Momentum">BrMom</th>
                <th nzWidth="70px" nz-tooltip="Vol Acceleration">VolAcc</th>
                <th nzWidth="60px">PosLmt</th>
                <th nzWidth="70px">Hold</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let r of histTable.data">
                <td nzLeft><strong>{{ r.trade_date }}</strong></td>
                <td><nz-tag [nzColor]="marketLabelColor(r.label_market)">{{ r.label_market || '-' }}</nz-tag></td>
                <td><nz-tag [nzColor]="volTagColor(r.label_vol)">{{ r.label_vol || '-' }}</nz-tag></td>
                <td [style.color]="dimTextColor(r.trend_strength)">{{ r.trend_strength | number:'1.2-2' }}</td>
                <td [style.color]="dimTextColor(r.risk_appetite)">{{ r.risk_appetite | number:'1.2-2' }}</td>
                <td [style.color]="dimTextColorInvert(r.volatility_stress)">{{ r.volatility_stress | number:'1.2-2' }}</td>
                <td [style.color]="dimTextColor(r.market_breadth)">{{ r.market_breadth | number:'1.2-2' }}</td>
                <td [style.color]="dimTextColor(r.liquidity)">{{ r.liquidity | number:'1.2-2' }}</td>
                <td>{{ r.sector_concentration | number:'1.2-2' }}</td>
                <td [style.color]="signalColor(r.breadth_momentum)">{{ r.breadth_momentum | number:'1.3-3' }}</td>
                <td [style.color]="signalColor(r.vol_acceleration)">{{ r.vol_acceleration | number:'1.3-3' }}</td>
                <td>{{ (r.position_limit || 0) * 100 | number:'1.0-0' }}%</td>
                <td>{{ r.suggested_holding_period || '-' }}</td>
              </tr>
            </tbody>
          </nz-table>
        </nz-card>
      </nz-tab>

      <!-- ==================== Tab 3: Features ==================== -->
      <nz-tab nzTitle="Features">
        <nz-card [nzBordered]="false">
          <div nz-row [nzGutter]="16" nzAlign="middle" style="margin-bottom: 16px;">
            <div nz-col>
              <label class="field-label">Trade Date</label>
              <input nz-input placeholder="YYYYMMDD" [(ngModel)]="featureDate" style="width: 140px;" />
            </div>
            <div nz-col>
              <button nz-button nzType="primary" (click)="loadFeatures()" [nzLoading]="loadingFeatures"
                      [disabled]="!featureDate">
                <span nz-icon nzType="search"></span> Query
              </button>
            </div>
          </div>

          <div *ngIf="features">
            <nz-descriptions nzBordered nzSize="small" [nzColumn]="2" nzTitle="Regime Features">
              <nz-descriptions-item nzTitle="Trade Date">{{ features.trade_date }}</nz-descriptions-item>
              <nz-descriptions-item nzTitle="HS300 Distance from MA120">
                <span [style.color]="features.hs300_distance_from_ma120 >= 0 ? '#52c41a' : '#ff4d4f'" style="font-family: monospace;">
                  {{ features.hs300_distance_from_ma120 | number:'1.4-4' }}
                </span>
              </nz-descriptions-item>
              <nz-descriptions-item nzTitle="HS300 MA20 Slope">
                <span [style.color]="features.hs300_ma20_slope >= 0 ? '#52c41a' : '#ff4d4f'" style="font-family: monospace;">
                  {{ features.hs300_ma20_slope | number:'1.4-4' }}
                </span>
              </nz-descriptions-item>
              <nz-descriptions-item nzTitle="Breadth Above MA20 %">
                <span style="font-family: monospace;">{{ features.breadth_above_ma20_pct | number:'1.2-2' }}</span>
              </nz-descriptions-item>
              <nz-descriptions-item nzTitle="Vol 20D">
                <span style="font-family: monospace;">{{ features.vol_20d | number:'1.4-4' }}</span>
              </nz-descriptions-item>
              <nz-descriptions-item nzTitle="Vol Ratio (20D/60D)">
                <span [style.color]="features.vol_ratio > 1.2 ? '#ff4d4f' : features.vol_ratio < 0.8 ? '#52c41a' : 'inherit'" style="font-family: monospace;">
                  {{ features.vol_ratio | number:'1.3-3' }}
                </span>
              </nz-descriptions-item>
              <nz-descriptions-item nzTitle="Turnover Ratio">
                <span style="font-family: monospace;">{{ features.turnover_ratio | number:'1.3-3' }}</span>
              </nz-descriptions-item>
              <nz-descriptions-item nzTitle="Style Small vs Large">
                <span [style.color]="features.style_small_vs_large >= 0 ? '#1677ff' : '#722ed1'" style="font-family: monospace;">
                  {{ features.style_small_vs_large | number:'1.4-4' }}
                </span>
              </nz-descriptions-item>
              <nz-descriptions-item nzTitle="Industry Concentration (HHI)">
                <span style="font-family: monospace;">{{ features.industry_concentration | number:'1.4-4' }}</span>
              </nz-descriptions-item>
            </nz-descriptions>
          </div>
          <nz-empty *ngIf="!features && !loadingFeatures" nzNotFoundContent="Enter trade date to query features"></nz-empty>
        </nz-card>
      </nz-tab>

      <!-- ==================== Tab 4: Compute ==================== -->
      <nz-tab nzTitle="Compute">
        <nz-card nzTitle="Single-Day Computation" [nzBordered]="false" style="margin-bottom: 16px;">
          <div nz-row [nzGutter]="16" nzAlign="middle">
            <div nz-col>
              <label class="field-label">Trade Date</label>
              <input nz-input placeholder="YYYYMMDD" [(ngModel)]="computeDate" style="width: 140px;" />
            </div>
            <div nz-col>
              <label class="field-label">Market</label>
              <nz-select [(ngModel)]="computeMarket" style="width: 100px;">
                <nz-option nzValue="zh_a" nzLabel="A股"></nz-option>
              </nz-select>
            </div>
            <div nz-col>
              <button nz-button nzType="primary" (click)="computeRegime()" [nzLoading]="computing">
                <span nz-icon nzType="thunderbolt"></span> Compute
              </button>
            </div>
          </div>
          <div *ngIf="computeResult" class="result-msg">
            ✅ Regime computed — {{ computeResult.label_market || 'done' }}
          </div>
        </nz-card>

        <nz-card nzTitle="Batch Backfill" [nzBordered]="false">
          <div nz-row [nzGutter]="16" nzAlign="middle">
            <div nz-col>
              <label class="field-label">Trading Dates (comma-separated)</label>
              <input nz-input placeholder="e.g. 20260101,20260102,20260103" [(ngModel)]="backfillDates" style="width: 400px;" />
            </div>
            <div nz-col>
              <button nz-button nzType="primary" (click)="backfill()" [nzLoading]="backfilling"
                      [disabled]="!backfillDates">
                <span nz-icon nzType="history"></span> Backfill
              </button>
            </div>
          </div>
          <div *ngIf="backfillResult" class="result-msg">
            ✅ Backfilled {{ backfillResult.count }} dates
          </div>
        </nz-card>
      </nz-tab>
    </nz-tabset>
  `,
  styles: [`
    .action-bar { margin-bottom: 12px; }
    .field-label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
    .result-msg { margin-top: 12px; padding: 8px 12px; background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 4px; color: #389e0d; }
    .dim-card { padding: 8px; border: 1px solid #f0f0f0; border-radius: 6px; }
    .dim-label { font-weight: 600; font-size: 13px; margin-bottom: 4px; }
    .dim-desc { font-size: 11px; color: #999; margin-top: 2px; }
    :host ::ng-deep .ant-card { margin-bottom: 0; }
  `]
})
export class RegimeEngineComponent implements OnInit {
  private svc = inject(RegimeService);
  private msg = inject(NzMessageService);

  // -- Current --
  current: RegimeResult | null = null;
  loadingCurrent = false;
  stateDimensions: { label: string; value: number; desc: string; invert?: boolean }[] = [];
  strategyWeightEntries: [string, number][] = [];
  factorAdjEntries: [string, number][] = [];

  // -- History --
  history: RegimeResult[] = [];
  historyLimit = 60;
  loadingHistory = false;

  // -- Features --
  featureDate = '';
  features: RegimeFeatures | null = null;
  loadingFeatures = false;

  // -- Compute --
  computeDate = '';
  computeMarket = 'zh_a';
  computing = false;
  computeResult: RegimeResult | null = null;

  // -- Backfill --
  backfillDates = '';
  backfilling = false;
  backfillResult: any = null;

  ngOnInit() {
    this.loadCurrent();
  }

  loadCurrent() {
    this.loadingCurrent = true;
    this.svc.getCurrent().subscribe({
      next: data => {
        this.current = data;
        this.buildStateDimensions(data);
        this.strategyWeightEntries = Object.entries(data.strategy_weights || {}).sort() as [string, number][];
        this.factorAdjEntries = Object.entries(data.factor_weight_adjustments || {}).sort() as [string, number][];
        this.loadingCurrent = false;
      },
      error: err => {
        this.current = null;
        this.loadingCurrent = false;
        if (err.status !== 404) this.msg.error('Failed to load current regime');
      }
    });
  }

  loadHistory() {
    this.loadingHistory = true;
    this.svc.getHistory(this.historyLimit).subscribe({
      next: data => { this.history = data; this.loadingHistory = false; },
      error: err => { this.msg.error('Failed to load history'); this.loadingHistory = false; }
    });
  }

  loadFeatures() {
    this.loadingFeatures = true;
    this.features = null;
    this.svc.getFeatures(this.featureDate).subscribe({
      next: data => { this.features = data; this.loadingFeatures = false; },
      error: err => {
        this.msg.error(err.status === 404 ? 'Features not found for this date' : 'Failed to load features');
        this.loadingFeatures = false;
      }
    });
  }

  computeRegime() {
    if (!this.computeDate) this.computeDate = this.todayStr();
    this.computing = true;
    this.computeResult = null;
    this.svc.compute(this.computeDate, this.computeMarket).subscribe({
      next: res => {
        this.computeResult = res;
        this.computing = false;
        this.msg.success('Regime computed');
        this.loadCurrent();
      },
      error: err => { this.msg.error('Compute failed: ' + (err.error?.detail || err.message)); this.computing = false; }
    });
  }

  backfill() {
    const dates = this.backfillDates.split(',').map(s => s.trim()).filter(s => s);
    if (!dates.length) { this.msg.warning('Please enter at least one date'); return; }
    this.backfilling = true;
    this.backfillResult = null;
    this.svc.backfill(dates).subscribe({
      next: res => { this.backfillResult = res; this.backfilling = false; this.msg.success('Backfill completed'); },
      error: err => { this.msg.error('Backfill failed: ' + (err.error?.detail || err.message)); this.backfilling = false; }
    });
  }

  // ── Helpers ──

  private buildStateDimensions(r: RegimeResult) {
    this.stateDimensions = [
      { label: 'Trend Strength', value: r.trend_strength, desc: '0=Strong Bear, 0.5=No Trend, 1=Strong Bull' },
      { label: 'Risk Appetite', value: r.risk_appetite, desc: '0=Risk-Off, 1=Risk-On' },
      { label: 'Volatility Stress', value: r.volatility_stress, desc: '0=Calm, 1=Extreme Vol', invert: true },
      { label: 'Market Breadth', value: r.market_breadth, desc: '0=Broad Decline, 1=Broad Rally' },
      { label: 'Liquidity', value: r.liquidity, desc: '0=Dry, 1=Flood' },
      { label: 'Sector Concentration', value: r.sector_concentration, desc: '0=Even, 1=Extreme Concentration', invert: true },
    ];
  }

  dimColor(value: number, invert?: boolean): string {
    const v = invert ? 1 - value : value;
    if (v >= 0.65) return '#52c41a';
    if (v >= 0.35) return '#faad14';
    return '#ff4d4f';
  }

  dimFormatter(value: number): (p: number) => string {
    return () => value.toFixed(2);
  }

  dimTextColor(value: number): string {
    if (value >= 0.65) return '#52c41a';
    if (value <= 0.35) return '#ff4d4f';
    return 'inherit';
  }

  dimTextColorInvert(value: number): string {
    if (value >= 0.65) return '#ff4d4f';
    if (value <= 0.35) return '#52c41a';
    return 'inherit';
  }

  signalColor(value: number): string {
    if (value > 0.1) return '#52c41a';
    if (value < -0.1) return '#ff4d4f';
    return '#888';
  }

  labelAlertType(label?: string): 'success' | 'info' | 'warning' | 'error' {
    switch (label) {
      case 'BULL_TREND': return 'success';
      case 'BEAR_TREND': return 'error';
      case 'PANIC': return 'error';
      case 'SIDEWAYS': return 'warning';
      default: return 'info';
    }
  }

  marketLabelColor(label?: string): string {
    switch (label) {
      case 'BULL_TREND': return 'green';
      case 'BEAR_TREND': return 'red';
      case 'PANIC': return 'magenta';
      case 'SIDEWAYS': return 'orange';
      default: return 'default';
    }
  }

  volTagColor(label?: string): string {
    switch (label) {
      case 'SPIKE': return 'magenta';
      case 'HIGH': return 'red';
      case 'NORMAL': return 'blue';
      case 'LOW': return 'green';
      default: return 'default';
    }
  }

  private todayStr(): string {
    const d = new Date();
    return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  }
}

