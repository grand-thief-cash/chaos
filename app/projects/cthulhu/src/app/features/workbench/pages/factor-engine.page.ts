import {Component, inject, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {NzCardModule} from 'ng-zorro-antd/card';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzInputModule} from 'ng-zorro-antd/input';
import {NzDatePickerModule} from 'ng-zorro-antd/date-picker';
import {NzSelectModule} from 'ng-zorro-antd/select';
import {NzTabsModule} from 'ng-zorro-antd/tabs';
import {NzTagModule} from 'ng-zorro-antd/tag';
import {NzSpinModule} from 'ng-zorro-antd/spin';
import {NzDividerModule} from 'ng-zorro-antd/divider';
import {NzEmptyModule} from 'ng-zorro-antd/empty';
import {NzToolTipModule} from 'ng-zorro-antd/tooltip';
import {NzIconModule} from 'ng-zorro-antd/icon';
import {NzDescriptionsModule} from 'ng-zorro-antd/descriptions';
import {NzInputNumberModule} from 'ng-zorro-antd/input-number';
import {NzMessageService} from 'ng-zorro-antd/message';
import {NzGridModule} from 'ng-zorro-antd/grid';

import {FactorService} from '../services/factor.service';
import {FactorMeta, FactorRankItem, FactorSnapshot} from '../models/factor.models';

@Component({
  selector: 'app-factor-engine',
  standalone: true,
  imports: [
    CommonModule, FormsModule,
    NzCardModule, NzTableModule, NzButtonModule, NzInputModule,
    NzDatePickerModule, NzSelectModule, NzTabsModule, NzTagModule,
    NzSpinModule, NzDividerModule, NzEmptyModule, NzToolTipModule,
    NzIconModule, NzDescriptionsModule, NzInputNumberModule, NzGridModule
  ],
  template: `
    <nz-tabset>
      <!-- ==================== Tab 1: Factor Meta ==================== -->
      <nz-tab nzTitle="Factor Registry">
        <nz-card [nzBordered]="false">
          <div class="action-bar">
            <button nz-button nzType="default" (click)="loadMeta()" [nzLoading]="loadingMeta">
              <span nz-icon nzType="reload"></span> Refresh
            </button>
          </div>
          <nz-table #metaTable [nzData]="factorMetas" [nzLoading]="loadingMeta"
                    nzSize="small" [nzPageSize]="50"
                    [nzShowSizeChanger]="true">
            <thead>
              <tr>
                <th nzWidth="140px">Name</th>
                <th nzWidth="120px">中文名</th>
                <th nzWidth="100px">Category</th>
                <th>Formula</th>
                <th nzWidth="60px">Unit</th>
                <th nzWidth="60px" nz-tooltip nzTooltipTitle="Higher is Better">H↑</th>
                <th nzWidth="80px">Mkt Data</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let f of metaTable.data">
                <td><strong>{{ f.name }}</strong></td>
                <td>{{ f.cn_name }}</td>
                <td>
                  <nz-tag [nzColor]="categoryColor(f.category)">{{ f.category }}</nz-tag>
                </td>
                <td style="font-family: monospace; font-size: 12px;">{{ f.formula }}</td>
                <td>{{ f.unit }}</td>
                <td>
                  <span *ngIf="f.higher_is_better" style="color:#52c41a;">✓</span>
                  <span *ngIf="!f.higher_is_better" style="color:#ff4d4f;">✗</span>
                </td>
                <td>
                  <nz-tag *ngIf="f.requires_market_data" nzColor="blue">Yes</nz-tag>
                  <nz-tag *ngIf="!f.requires_market_data">No</nz-tag>
                </td>
              </tr>
            </tbody>
          </nz-table>
        </nz-card>
      </nz-tab>

      <!-- ==================== Tab 2: Compute ==================== -->
      <nz-tab nzTitle="Compute">
        <nz-card nzTitle="Full Computation" [nzBordered]="false" style="margin-bottom: 16px;">
          <div nz-row [nzGutter]="16" nzAlign="middle">
            <div nz-col>
              <label class="field-label">Date</label>
              <input nz-input placeholder="YYYYMMDD" [(ngModel)]="computeDate" style="width: 140px;" />
            </div>
            <div nz-col>
              <label class="field-label">Market</label>
              <nz-select [(ngModel)]="computeMarket" style="width: 100px;">
                <nz-option nzValue="zh_a" nzLabel="A股"></nz-option>
              </nz-select>
            </div>
            <div nz-col>
              <button nz-button nzType="primary" (click)="computeFull()" [nzLoading]="computing">
                <span nz-icon nzType="thunderbolt"></span> Run Full
              </button>
            </div>
          </div>
          <div *ngIf="computeResult" class="result-msg">
            ✅ Computed {{ computeResult.symbols_count }} symbols for {{ computeResult.as_of_date }}
          </div>
        </nz-card>

        <nz-card nzTitle="Incremental Computation" [nzBordered]="false">
          <div nz-row [nzGutter]="16" nzAlign="middle">
            <div nz-col>
              <label class="field-label">Symbols (comma-separated)</label>
              <input nz-input placeholder="e.g. 000001,000002" [(ngModel)]="incrSymbols" style="width: 260px;" />
            </div>
            <div nz-col>
              <label class="field-label">Date</label>
              <input nz-input placeholder="YYYYMMDD" [(ngModel)]="incrDate" style="width: 140px;" />
            </div>
            <div nz-col>
              <button nz-button nzType="primary" (click)="computeIncremental()" [nzLoading]="computingIncr"
                      [disabled]="!incrSymbols">
                <span nz-icon nzType="thunderbolt"></span> Run Incremental
              </button>
            </div>
          </div>
          <div *ngIf="incrResult" class="result-msg">
            ✅ Computed {{ incrResult.symbols_count }} symbols
          </div>
        </nz-card>
      </nz-tab>

      <!-- ==================== Tab 3: Snapshot ==================== -->
      <nz-tab nzTitle="Snapshot">
        <nz-card [nzBordered]="false">
          <div nz-row [nzGutter]="16" nzAlign="middle" style="margin-bottom: 16px;">
            <div nz-col>
              <label class="field-label">Symbol</label>
              <input nz-input placeholder="e.g. 000001" [(ngModel)]="snapSymbol" style="width: 120px;" />
            </div>
            <div nz-col>
              <label class="field-label">Date</label>
              <input nz-input placeholder="YYYYMMDD" [(ngModel)]="snapDate" style="width: 140px;" />
            </div>
            <div nz-col>
              <button nz-button nzType="primary" (click)="loadSnapshot()" [nzLoading]="loadingSnap"
                      [disabled]="!snapSymbol || !snapDate">
                <span nz-icon nzType="search"></span> Query
              </button>
            </div>
          </div>

          <div *ngIf="snapshot">
            <nz-divider nzText="Raw Factors" nzOrientation="left"></nz-divider>
            <nz-table #rawTable [nzData]="snapshotRawEntries" nzSize="small" [nzShowPagination]="false" [nzBordered]="true">
              <thead><tr><th nzWidth="200px">Factor</th><th>Value</th></tr></thead>
              <tbody>
                <tr *ngFor="let e of rawTable.data">
                  <td style="font-weight: 500;">{{ e[0] }}</td>
                  <td style="font-family: monospace;">{{ e[1] | number:'1.4-4' }}</td>
                </tr>
              </tbody>
            </nz-table>

            <nz-divider nzText="Normalized Factors" nzOrientation="left"></nz-divider>
            <nz-table #normTable [nzData]="snapshotNormEntries" nzSize="small" [nzShowPagination]="false" [nzBordered]="true">
              <thead><tr><th nzWidth="200px">Factor</th><th>Value</th></tr></thead>
              <tbody>
                <tr *ngFor="let e of normTable.data">
                  <td style="font-weight: 500;">{{ e[0] }}</td>
                  <td style="font-family: monospace;">{{ e[1] | number:'1.4-4' }}</td>
                </tr>
              </tbody>
            </nz-table>
          </div>
          <nz-empty *ngIf="!snapshot && !loadingSnap" nzNotFoundContent="Enter symbol and date to query snapshot"></nz-empty>
        </nz-card>
      </nz-tab>

      <!-- ==================== Tab 4: Ranking ==================== -->
      <nz-tab nzTitle="Ranking">
        <nz-card [nzBordered]="false">
          <div nz-row [nzGutter]="16" nzAlign="middle" style="margin-bottom: 16px;">
            <div nz-col>
              <label class="field-label">Factor</label>
              <nz-select [(ngModel)]="rankFactor" style="width: 200px;" nzShowSearch nzPlaceHolder="Select factor">
                <nz-option *ngFor="let f of factorMetas" [nzValue]="f.name" [nzLabel]="f.name + ' (' + f.cn_name + ')'"></nz-option>
              </nz-select>
            </div>
            <div nz-col>
              <label class="field-label">Date</label>
              <input nz-input placeholder="YYYYMMDD" [(ngModel)]="rankDate" style="width: 140px;" />
            </div>
            <div nz-col>
              <label class="field-label">Top N</label>
              <nz-input-number [(ngModel)]="rankTopN" [nzMin]="1" [nzMax]="500" [nzStep]="10" style="width: 80px;"></nz-input-number>
            </div>
            <div nz-col>
              <button nz-button nzType="primary" (click)="loadRanking()" [nzLoading]="loadingRank"
                      [disabled]="!rankFactor || !rankDate">
                <span nz-icon nzType="ordered-list"></span> Query
              </button>
            </div>
          </div>

          <nz-table #rankTable [nzData]="rankItems" [nzLoading]="loadingRank" nzSize="small" [nzPageSize]="50">
            <thead><tr><th nzWidth="60px">#</th><th nzWidth="120px">Symbol</th><th>{{ rankFactor || 'Value' }}</th></tr></thead>
            <tbody>
              <tr *ngFor="let item of rankTable.data; let i = index">
                <td>{{ i + 1 }}</td>
                <td><strong>{{ item.symbol }}</strong></td>
                <td style="font-family: monospace;">{{ getRankValue(item) | number:'1.4-4' }}</td>
              </tr>
            </tbody>
          </nz-table>
          <nz-empty *ngIf="rankItems.length === 0 && !loadingRank" nzNotFoundContent="Select factor and date to view ranking"></nz-empty>
        </nz-card>
      </nz-tab>
    </nz-tabset>
  `,
  styles: [`
    .action-bar { margin-bottom: 12px; }
    .field-label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
    .result-msg { margin-top: 12px; padding: 8px 12px; background: #f6ffed; border: 1px solid #b7eb8f; border-radius: 4px; color: #389e0d; }
    :host ::ng-deep .ant-card { margin-bottom: 0; }
  `]
})
export class FactorEngineComponent implements OnInit {
  private svc = inject(FactorService);
  private msg = inject(NzMessageService);

  // -- Meta --
  factorMetas: FactorMeta[] = [];
  loadingMeta = false;

  // -- Compute Full --
  computeDate = '';
  computeMarket = 'zh_a';
  computing = false;
  computeResult: any = null;

  // -- Compute Incremental --
  incrSymbols = '';
  incrDate = '';
  computingIncr = false;
  incrResult: any = null;

  // -- Snapshot --
  snapSymbol = '';
  snapDate = '';
  loadingSnap = false;
  snapshot: FactorSnapshot | null = null;
  snapshotRawEntries: [string, number][] = [];
  snapshotNormEntries: [string, number][] = [];

  // -- Ranking --
  rankFactor = '';
  rankDate = '';
  rankTopN = 50;
  loadingRank = false;
  rankItems: FactorRankItem[] = [];

  ngOnInit() {
    this.loadMeta();
  }

  loadMeta() {
    this.loadingMeta = true;
    this.svc.getMeta().subscribe({
      next: data => { this.factorMetas = data; this.loadingMeta = false; },
      error: () => { this.msg.error('Failed to load factor meta'); this.loadingMeta = false; }
    });
  }

  computeFull() {
    if (!this.computeDate) {
      this.computeDate = this.todayStr();
    }
    this.computing = true;
    this.computeResult = null;
    this.svc.computeFull(this.computeDate, this.computeMarket).subscribe({
      next: res => { this.computeResult = res; this.computing = false; this.msg.success('Full computation completed'); },
      error: err => { this.msg.error('Computation failed: ' + (err.error?.detail || err.message)); this.computing = false; }
    });
  }

  computeIncremental() {
    if (!this.incrDate) this.incrDate = this.todayStr();
    const symbols = this.incrSymbols.split(',').map(s => s.trim()).filter(s => s);
    if (!symbols.length) { this.msg.warning('Please enter at least one symbol'); return; }
    this.computingIncr = true;
    this.incrResult = null;
    this.svc.computeIncremental(symbols, this.incrDate).subscribe({
      next: res => { this.incrResult = res; this.computingIncr = false; this.msg.success('Incremental computation completed'); },
      error: err => { this.msg.error('Computation failed: ' + (err.error?.detail || err.message)); this.computingIncr = false; }
    });
  }

  loadSnapshot() {
    this.loadingSnap = true;
    this.snapshot = null;
    this.svc.getSnapshot(this.snapSymbol, this.snapDate).subscribe({
      next: data => {
        this.snapshot = data;
        this.snapshotRawEntries = Object.entries(data.raw_factors || {}).sort() as [string, number][];
        this.snapshotNormEntries = Object.entries(data.norm_factors || {}).sort() as [string, number][];
        this.loadingSnap = false;
      },
      error: err => {
        this.msg.error(err.status === 404 ? 'Snapshot not found' : 'Failed to load snapshot');
        this.loadingSnap = false;
      }
    });
  }

  loadRanking() {
    this.loadingRank = true;
    this.rankItems = [];
    this.svc.getRanking(this.rankFactor, this.rankDate, 'zh_a', this.rankTopN).subscribe({
      next: data => { this.rankItems = data; this.loadingRank = false; },
      error: () => { this.msg.error('Failed to load ranking'); this.loadingRank = false; }
    });
  }

  getRankValue(item: FactorRankItem): number {
    const val = item[this.rankFactor];
    return typeof val === 'number' ? val : 0;
  }

  categoryColor(cat: string): string {
    const map: Record<string, string> = {
      value: 'blue', growth: 'green', quality: 'purple', momentum: 'orange',
      size: 'cyan', volatility: 'red', dividend: 'gold', leverage: 'magenta'
    };
    return map[cat?.toLowerCase()] || 'default';
  }

  private todayStr(): string {
    const d = new Date();
    return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  }
}

