import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, Subscription } from 'rxjs';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { ArtemisBiService } from '../services/artemis-bi.service';
import {
  BIFieldDiscoveryEntry,
  BIFieldMeta,
  BIRawQueryResponse,
} from '../models/bi-simple.models';

@Component({
  selector: 'app-bi-raw-data-explorer-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzCardModule,
    NzButtonModule,
    NzTableModule,
    NzSpinModule,
    NzTagModule,
    NzEmptyModule,
  ],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <nz-card [nzTitle]="headerTpl" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <ng-template #headerTpl>
          <div style="display: flex; align-items: center; gap: 12px;">
            <span>原始数据 · {{ symbol }}</span>
            <nz-tag nzColor="blue">{{ dataset }} / {{ dataType }}</nz-tag>
            <button nz-button nzSize="small" (click)="goBack()">← 返回公司页</button>
          </div>
        </ng-template>

        <div style="display: flex; flex-direction: column; gap: 14px;">
          <div style="display: flex; gap: 16px; flex-wrap: wrap; align-items: end;">
            @if (isFinancialStatement) {
              <div>
                <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">报告类型</label>
                <select [(ngModel)]="reportType" (ngModelChange)="onFilterChange()" class="rde-native-select" style="width: 140px;">
                  <option [ngValue]="null">全部</option>
                  <option *ngFor="let opt of reportTypeOptions" [ngValue]="opt.value">{{ opt.label }}</option>
                </select>
              </div>

              <div>
                <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">报表类型</label>
                <select [(ngModel)]="statementCode" (ngModelChange)="onFilterChange()" class="rde-native-select" style="width: 160px;">
                  <option [ngValue]="null">全部</option>
                  <option *ngFor="let opt of statementCodeOptions" [ngValue]="opt.value">{{ opt.label }}</option>
                </select>
              </div>
            }

            @if (isEquityStructure) {
              <div>
                <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">变动日 起</label>
                <input type="date" [(ngModel)]="periodStart" (ngModelChange)="onFilterChange()" class="rde-native-input" style="width: 160px;" />
              </div>

              <div>
                <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">变动日 止</label>
                <input type="date" [(ngModel)]="periodEnd" (ngModelChange)="onFilterChange()" class="rde-native-input" style="width: 160px;" />
              </div>
            } @else {
              <div>
                <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">报告期 起</label>
                <input type="date" [(ngModel)]="periodStart" (ngModelChange)="onFilterChange()" class="rde-native-input" style="width: 160px;" />
              </div>

              <div>
                <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">报告期 止</label>
                <input type="date" [(ngModel)]="periodEnd" (ngModelChange)="onFilterChange()" class="rde-native-input" style="width: 160px;" />
              </div>
            }

            <div>
              <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">每页</label>
              <select [(ngModel)]="pageSize" (ngModelChange)="onPageSizeChange()" class="rde-native-select" style="width: 110px;">
                <option *ngFor="let opt of pageSizeOptions" [ngValue]="opt.value">{{ opt.label }}</option>
              </select>
            </div>

            <div>
              <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">&nbsp;</label>
              <button nz-button (click)="onResetFilters()">重置筛选</button>
            </div>
          </div>

          <div>
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
              <label style="font-size: 12px; color: #595959;">字段（多选，留空则取所有核心字段；{{ fieldOptions.length }} 个可选）</label>
              <button nz-button nzSize="small" nzType="link" (click)="toggleCoreFields()">
                {{ allCoreSelected ? '清空' : '选所有核心字段' }}
              </button>
            </div>
            <div style="max-height: 220px; overflow-y: auto; border: 1px solid #d9d9d9; border-radius: 4px; padding: 8px 12px; background: #fafafa;">
              @if (fieldOptions.length === 0) {
                <div style="color: #bfbfbf; font-size: 12px;">字段列表加载中…</div>
              } @else {
                <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 4px 16px;">
                  @for (f of fieldOptions; track f.raw_field) {
                    <label style="display: flex; align-items: center; gap: 6px; font-size: 13px; cursor: pointer; padding: 2px 0;">
                      <input type="checkbox"
                             [checked]="selectedFields.includes(f.query_name || f.canonical_field)"
                             (change)="toggleField(f.query_name || f.canonical_field)" />
                      <span [style.color]="f.is_core ? '#1890ff' : '#595959'" [style.font-weight]="f.is_core ? '500' : 'normal'">
                        {{ f.label_zh }}
                      </span>
                      <span style="color: #bfbfbf; font-size: 11px;">({{ f.query_name || f.canonical_field }})</span>
                    </label>
                  }
                </div>
              }
            </div>
            @if (selectedFields.length > 0) {
              <div style="margin-top: 6px; font-size: 12px; color: #595959;">已选 {{ selectedFields.length }} 个字段</div>
            }
          </div>
        </div>
      </nz-card>

      <nz-card nzTitle="查询结果" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        @if (loading) {
          <nz-spin nzTip="加载中..."></nz-spin>
        } @else if (response && response.rows.length > 0) {
          <nz-table #tbl [nzData]="response.rows" nzSize="small" [nzFrontPagination]="false"
                    [nzPageSize]="pageSize" [nzTotal]="response.total" [nzPageIndex]="pageIndex"
                    (nzPageIndexChange)="onPageChange($event)" [nzShowSizeChanger]="false"
                    [nzScroll]="{ x: scrollX }">
            <thead>
              <tr>
                @for (f of response.fields; track f.name) {
                  <th style="white-space: nowrap;" [title]="f.label_zh">
                    {{ f.label_zh || f.name }}
                    @if (f.unit) { <span style="color: #bfbfbf; font-weight: normal;">({{ f.unit }})</span> }
                  </th>
                }
              </tr>
            </thead>
            <tbody>
              @for (row of tbl.data; track $index) {
                <tr>
                  @for (f of response.fields; track f.name) {
                    <td style="white-space: nowrap;">{{ formatCell(row[f.name], f) }}</td>
                  }
                </tr>
              }
            </tbody>
          </nz-table>
          <div style="margin-top: 12px; color: #8c8c8c; font-size: 12px;">
            共 {{ response.total }} 条，第 {{ pageIndex }} 页 / {{ totalPages }} 页
          </div>
        } @else if (response) {
          <nz-empty nzNotFoundContent="没有符合条件的数据"></nz-empty>
        } @else {
          <nz-empty nzNotFoundContent="无法加载数据"></nz-empty>
        }
      </nz-card>
    </div>
  `,
  styles: [`
    .rde-native-select, .rde-native-input {
      height: 32px;
      padding: 4px 8px;
      border: 1px solid #d9d9d9;
      border-radius: 4px;
      font-size: 14px;
      background: #fff;
      color: rgba(0,0,0,0.85);
      outline: none;
    }
    .rde-native-select:focus, .rde-native-input:focus {
      border-color: #1890ff;
      box-shadow: 0 0 0 2px rgba(24,144,255,0.2);
    }
  `],
})
export class RawDataExplorerPageComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ArtemisBiService);

  symbol = '';
  market = 'zh_a';
  dataset = '';
  dataType = '';

  loading = false;
  response: BIRawQueryResponse | null = null;

  reportType: string | null = null;
  statementCode: string | null = null;
  periodStart = '';
  periodEnd = '';
  pageIndex = 1;
  pageSize: number = 50;

  fieldOptions: BIFieldDiscoveryEntry[] = [];
  selectedFields: string[] = [];

  reportTypeOptions = [
    { value: '1', label: '一季报' },
    { value: '2', label: '半年报' },
    { value: '3', label: '三季报' },
    { value: '4', label: '年报' },
  ];

  statementCodeOptions = [
    { value: '1', label: '合并报表' },
    { value: '2', label: '母公司报表' },
  ];

  pageSizeOptions = [
    { value: 20, label: '20 条' },
    { value: 50, label: '50 条' },
    { value: 100, label: '100 条' },
    { value: 200, label: '200 条' },
  ];

  private paramsSub?: Subscription;

  get totalPages(): number {
    return Math.max(1, Math.ceil((this.response?.total || 0) / this.pageSize));
  }

  get allCoreSelected(): boolean {
    const core = this.fieldOptions.filter((f) => f.is_core).map((f) => f.query_name || f.canonical_field);
    return core.length > 0 && core.every((c) => this.selectedFields.includes(c));
  }

  get scrollX(): string {
    const totalCols = this.response?.fields.length || 0;
    return `${Math.max(800, totalCols * 140)}px`;
  }

  get isFinancialStatement(): boolean {
    return this.dataset === 'financial_statement';
  }

  get isEquityStructure(): boolean {
    return this.dataset === 'equity_structure';
  }

  ngOnInit(): void {
    this.paramsSub = this.route.paramMap.subscribe((params) => {
      this.symbol = params.get('symbol') || '';
      this.dataset = params.get('dataset') || '';
      this.dataType = params.get('type') || '';
      this.market = this.route.snapshot.queryParamMap.get('market') || 'zh_a';
      if (this.symbol && this.dataset && this.dataType) {
        this.loadFields();
        this.onFilterChange();
      }
    });
  }

  ngOnDestroy(): void {
    this.paramsSub?.unsubscribe();
  }

  loadFields(): void {
    this.api.getDatasetFields(this.dataset, { type: this.dataType, include: 'all' }).subscribe({
      next: (resp) => {
        this.fieldOptions = resp.fields || [];
        this.loadEnumMaps();
      },
      error: () => {
        this.fieldOptions = [];
      },
    });
  }

  /**
   * Pre-fetch enum values for every enum_ref on the field list, so the table
   * can render code -> label_zh without an extra round-trip per cell.
   */
  private enumMaps: Record<string, Record<string, string>> = {};
  private loadEnumMaps(): void {
    const enumRefs = new Set<string>();
    for (const f of this.fieldOptions) {
      if (f.enum_ref) enumRefs.add(f.enum_ref);
    }
    for (const ref of enumRefs) {
      if (this.enumMaps[ref]) continue;
      this.api.getEnum(ref).subscribe({
        next: (resp) => {
          const map: Record<string, string> = {};
          for (const v of resp.values) map[v.code] = v.label_zh;
          this.enumMaps[ref] = map;
        },
        error: () => {
          this.enumMaps[ref] = {};
        },
      });
    }
  }

  toggleField(queryName: string): void {
    const idx = this.selectedFields.indexOf(queryName);
    if (idx >= 0) {
      this.selectedFields = this.selectedFields.filter((f) => f !== queryName);
    } else {
      this.selectedFields = [...this.selectedFields, queryName];
    }
    this.onFilterChange();
  }

  toggleCoreFields(): void {
    if (this.allCoreSelected) {
      this.selectedFields = [];
    } else {
      this.selectedFields = this.fieldOptions
        .filter((f) => f.is_core)
        .map((f) => f.query_name || f.canonical_field);
    }
    this.onFilterChange();
  }

  onResetFilters(): void {
    this.reportType = null;
    this.statementCode = null;
    this.periodStart = '';
    this.periodEnd = '';
    this.pageIndex = 1;
    this.onFilterChange();
  }

  onPageSizeChange(): void {
    this.pageIndex = 1;
    this.onFilterChange();
  }

  onPageChange(idx: number): void {
    this.pageIndex = idx;
    this.onFilterChange();
  }

  onFilterChange(): void {
    this.loading = true;
    const fields = this.selectedFields.length > 0 ? this.selectedFields.join(',') : undefined;
    const obs = this.buildQuery(fields);

    obs.subscribe({
      next: (resp) => {
        this.response = resp;
        this.loading = false;
      },
      error: () => {
        this.response = null;
        this.loading = false;
      },
    });
  }

  private buildQuery(fields: string | undefined): Observable<BIRawQueryResponse> {
    const common = {
      source: 'amazing_data',
      symbol: this.symbol,
      market: this.market,
      fields,
      format: 'flat' as const,
      page: this.pageIndex,
      page_size: this.pageSize,
    };

    if (this.isEquityStructure) {
      return this.api.queryEquityStructure({
        ...common,
        change_start: this.periodStart || undefined,
        change_end: this.periodEnd || undefined,
      });
    }

    if (this.dataset === 'corporate_action') {
      return this.api.queryCorporateAction({
        ...common,
        action_type: this.dataType,
        period_start: this.periodStart || undefined,
        period_end: this.periodEnd || undefined,
      });
    }

    return this.api.queryFinancial({
      ...common,
      statement_type: this.dataType,
      period_start: this.periodStart || undefined,
      period_end: this.periodEnd || undefined,
      report_type: this.reportType || undefined,
      statement_code: this.statementCode || undefined,
    });
  }

  goBack(): void {
    this.router.navigate(['/bi/company', this.symbol], { queryParams: { market: this.market } });
  }

  formatCell(v: unknown, field?: BIFieldMeta): string {
    if (v === null || v === undefined || v === '') return '-';
    if (field?.enum_ref) {
      const map = this.enumMaps[field.enum_ref];
      if (map && map[String(v)] !== undefined) return map[String(v)];
    }
    if (typeof v === 'number') {
      return Number.isInteger(v) ? String(v) : v.toFixed(4);
    }
    return String(v);
  }
}
