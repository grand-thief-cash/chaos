import {Component, inject, OnDestroy, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {Router} from '@angular/router';
import {FormsModule} from '@angular/forms';
import {PhoenixAService} from '../services/phoenixa.service';
import {
  CatalogOverview,
  TableCatalogEntry,
  GraphCatalogOverview,
  BusinessOverview,
  BusinessDomain
} from '../models/phoenixa.models';
import {NzCardModule} from 'ng-zorro-antd/card';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzStatisticModule} from 'ng-zorro-antd/statistic';
import {NzGridModule} from 'ng-zorro-antd/grid';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzTagModule} from 'ng-zorro-antd/tag';
import {NzInputModule} from 'ng-zorro-antd/input';
import {NzSelectModule} from 'ng-zorro-antd/select';
import {NzToolTipModule} from 'ng-zorro-antd/tooltip';
import {NzBadgeModule} from 'ng-zorro-antd/badge';
import {NzProgressModule} from 'ng-zorro-antd/progress';
import {NzSpinModule} from 'ng-zorro-antd/spin';
import {NzEmptyModule} from 'ng-zorro-antd/empty';
import {NzIconModule} from 'ng-zorro-antd/icon';
import {NzCollapseModule} from 'ng-zorro-antd/collapse';
import {NgxEchartsModule} from 'ngx-echarts';
import type {EChartsOption} from 'echarts';

@Component({
  selector: 'app-data-catalog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzCardModule,
    NzTableModule,
    NzStatisticModule,
    NzGridModule,
    NzButtonModule,
    NzTagModule,
    NzInputModule,
    NzSelectModule,
    NzToolTipModule,
    NzBadgeModule,
    NzProgressModule,
    NzSpinModule,
    NzEmptyModule,
    NzIconModule,
    NzCollapseModule,
    NgxEchartsModule
  ],
  template: `
    <nz-spin [nzSpinning]="loading" nzTip="Loading catalog...">

      <!-- Summary Stats -->
      <nz-card nzTitle="数据目录总览" [nzExtra]="headerExtra" style="margin-bottom: 16px;">
        <ng-template #headerExtra>
          <nz-badge *ngIf="overview?.cached" nzStatus="processing" nzText="Cached"></nz-badge>
          <button nz-button nzType="link" nz-tooltip nzTooltipTitle="Force refresh from database"
                  (click)="refresh(true)">
            <span nz-icon nzType="reload"></span> Refresh
          </button>
        </ng-template>

        <div nz-row [nzGutter]="16" style="margin-bottom: 24px;">
          <div nz-col [nzSpan]="6">
            <nz-statistic [nzValue]="overview?.summary?.total_tables ?? 0"
                          nzTitle="Total Tables"></nz-statistic>
          </div>
          <div nz-col [nzSpan]="6">
            <nz-statistic [nzValue]="formatRows(overview?.summary?.total_rows ?? 0)"
                          nzTitle="Total Rows"></nz-statistic>
          </div>
          <div nz-col [nzSpan]="6">
            <nz-statistic [nzValue]="overview?.summary?.total_disk_size ?? '-'"
                          nzTitle="Data Size"></nz-statistic>
          </div>
          <div nz-col [nzSpan]="6">
            <nz-statistic [nzValue]="overview?.summary?.total_index_size ?? '-'"
                          nzTitle="Index Size"></nz-statistic>
          </div>
        </div>

        <!-- Charts Row -->
        <div nz-row [nzGutter]="16">
          <div nz-col [nzSpan]="10">
            <nz-card nzTitle="存储分布" nzSize="small" [nzBordered]="false">
              @if (storagePieOptions) {
                <div echarts [options]="storagePieOptions" style="height: 260px; width: 100%;"></div>
              }
            </nz-card>
          </div>
          <div nz-col [nzSpan]="14">
            <nz-card nzTitle="按域统计" nzSize="small" [nzBordered]="false">
              @if (domainBarOptions) {
                <div echarts [options]="domainBarOptions" style="height: 260px; width: 100%;"></div>
              }
            </nz-card>
          </div>
        </div>
      </nz-card>

      <!-- Neo4j Graph Stats -->
      @if (graphCatalog?.available && graphCatalog; as graph) {
        <nz-card nzTitle="Neo4j 知识图谱" [nzExtra]="graphExtra" style="margin-bottom: 16px;">
          <ng-template #graphExtra>
            <nz-tag nzColor="green">Connected</nz-tag>
          </ng-template>
          <div nz-row [nzGutter]="16" style="margin-bottom: 16px;">
            <div nz-col [nzSpan]="8">
              <nz-statistic [nzValue]="graph.total_nodes" nzTitle="Total Nodes"></nz-statistic>
            </div>
            <div nz-col [nzSpan]="8">
              <nz-statistic [nzValue]="graph.total_edges" nzTitle="Total Edges"></nz-statistic>
            </div>
            <div nz-col [nzSpan]="8">
              <nz-statistic [nzValue]="graph.labels?.length ?? 0" nzTitle="Node Labels"></nz-statistic>
            </div>
          </div>
          <div nz-row [nzGutter]="16">
            <div nz-col [nzSpan]="12">
              <h4 style="margin-bottom: 8px;">Node Labels</h4>
              <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                <nz-tag *ngFor="let l of graph.labels || []" nzColor="geekblue">
                  {{ l.label }}: {{ l.count }}
                  @if (l.description) { <span style="color:#999; margin-left:4px;">({{ l.description }})</span> }
                </nz-tag>
              </div>
            </div>
            <div nz-col [nzSpan]="12">
              <h4 style="margin-bottom: 8px;">Relationship Types</h4>
              <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                <nz-tag *ngFor="let r of graph.rel_types || []" nzColor="purple">
                  {{ r.type }}: {{ r.count }}
                </nz-tag>
              </div>
            </div>
          </div>
        </nz-card>
      } @else if (graphCatalog && !graphCatalog.available) {
        <nz-card nzTitle="Neo4j 知识图谱" style="margin-bottom: 16px;">
          <nz-tag nzColor="default">Not Connected</nz-tag>
          <span style="color: #999; margin-left: 8px;">Neo4j is not enabled or unreachable</span>
        </nz-card>
      }

      <!-- Business Domain Overview -->
      @if (businessOverview?.domains?.length) {
        <nz-card nzTitle="业务数据概览" style="margin-bottom: 16px;">
          <nz-collapse>
            @for (d of businessOverview!.domains; track d.domain) {
              <nz-collapse-panel [nzHeader]="d.label + ' \u2014 ' + d.description + ' (' + d.table_count + ' \u8868, ' + formatRows(d.total_rows) + ' \u884C)'">
                <div style="margin-bottom: 12px;">
                  <span style="color: #666;">{{ d.description }}</span>
                </div>
                @if (d.tables.length) {
                  <div style="margin-bottom: 10px;">
                    <strong>\u6570\u636E\u8868\uFF1A</strong>
                    @for (t of d.tables; track t) {
                      <nz-tag nzColor="blue" style="cursor: pointer; margin: 2px 0;"
                              (click)="goToDetailByName(t)">{{ t }}</nz-tag>
                    }
                  </div>
                }
                @if (d.api_endpoints?.length) {
                  <div style="margin-bottom: 10px;">
                    <strong>API \u7AEF\u70B9\uFF1A</strong>
                    @for (ep of d.api_endpoints; track ep.path + ep.method) {
                      <div style="margin: 4px 0; display: flex; align-items: center; gap: 6px;">
                        <nz-tag [nzColor]="ep.method === 'GET' ? 'blue' : 'green'"
                                style="min-width: 44px; text-align: center;">{{ ep.method }}</nz-tag>
                        <code>{{ ep.path }}</code>
                        <span style="color: #999; font-size: 12px;">{{ ep.description }}</span>
                      </div>
                    }
                  </div>
                }
                @if (d.example_calls?.length) {
                  <div style="margin-bottom: 10px;">
                    <strong>\u793A\u4F8B\u8C03\u7528\uFF1A</strong>
                    @for (ex of d.example_calls; track ex.title) {
                      <div style="margin: 4px 0;">
                        <span style="color: #666; margin-right: 4px;">{{ ex.title }}:</span>
                        <code style="background: #f0f5ff; padding: 2px 6px; border-radius: 3px;">{{ ex.url }}</code>
                      </div>
                    }
                  </div>
                }
                @if (d.cross_refs?.length) {
                  <div>
                    <strong>\u5173\u8054\u8868\uFF1A</strong>
                    @for (cr of d.cross_refs; track cr.to_table) {
                      <nz-tag nzColor="geekblue" style="margin: 2px;">
                        {{ cr.to_table }} <span style="color:#999;">({{ cr.join_key }}) {{ cr.description }}</span>
                      </nz-tag>
                    }
                  </div>
                }
              </nz-collapse-panel>
            }
          </nz-collapse>
        </nz-card>
      }

      <!-- Tables List -->
      <nz-card nzTitle="\u6570\u636E\u8868\u8BE6\u60C5" [nzExtra]="filterExtra">
        <ng-template #filterExtra>
          <div style="display: flex; gap: 8px; align-items: center;">
            <nz-input-group [nzPrefix]="searchIcon" style="width: 200px;">
              <input nz-input placeholder="Search tables..." [(ngModel)]="searchText"
                     (ngModelChange)="filterTables()" />
            </nz-input-group>
            <ng-template #searchIcon><span nz-icon nzType="search"></span></ng-template>
            <nz-select [(ngModel)]="selectedDomain" (ngModelChange)="filterTables()"
                       nzPlaceHolder="All Domains" nzAllowClear style="width: 150px;">
              <nz-option *ngFor="let d of domainOptions" [nzValue]="d" [nzLabel]="d"></nz-option>
            </nz-select>
          </div>
        </ng-template>

        <nz-table #tableRef [nzData]="filteredTables" nzSize="small"
                  [nzShowSizeChanger]="true" [nzPageSize]="20"
                  [nzFrontPagination]="true">
          <thead>
            <tr>
              <th nzWidth="80px">Domain</th>
              <th>Table</th>
              <th>Description</th>
              <th nzAlign="right" nzWidth="100px">Rows</th>
              <th nzAlign="right" nzWidth="90px">Data</th>
              <th nzAlign="right" nzWidth="90px">Index</th>
              <th nzWidth="60px">Tier</th>
              <th nzWidth="180px">Time Range</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let t of tableRef.data" style="cursor: pointer;"
                (click)="goToDetail(t)">
              <td>
                <nz-tag [nzColor]="getDomainColor(t.domain)">{{ t.domain }}</nz-tag>
              </td>
              <td>
                <code>{{ t.table_name }}</code>
                <nz-tag *ngIf="t.is_hypertable" nzColor="blue" style="margin-left: 4px;">TS</nz-tag>
                <nz-tag *ngIf="t.has_jsonb" nzColor="purple" style="margin-left: 4px;">JSONB</nz-tag>
              </td>
              <td style="color: #666;">{{ t.description }}</td>
              <td nzAlign="right">{{ formatRows(t.row_count) }}</td>
              <td nzAlign="right">{{ t.disk_size }}</td>
              <td nzAlign="right">{{ t.index_size }}</td>
              <td>
                <nz-tag [nzColor]="t.storage_tier === 'hot' ? 'volcano' : 'cyan'">
                  {{ t.storage_tier === 'hot' ? '🔥 Hot' : '❄️ Warm' }}
                </nz-tag>
              </td>
              <td style="font-size: 12px; color: #999;">
                @if (t.time_range) {
                  {{ t.time_range.min }} ~ {{ t.time_range.max }}
                } @else {
                  —
                }
              </td>
            </tr>
          </tbody>
        </nz-table>
      </nz-card>

    </nz-spin>
  `,
  styles: [`
    :host { display: block; padding: 16px; }
    nz-card { border-radius: 8px; }
    code { font-size: 12px; background: #f5f5f5; padding: 2px 4px; border-radius: 3px; }
  `]
})
export class DataCatalogComponent implements OnInit, OnDestroy {
  private service = inject(PhoenixAService);
  private router = inject(Router);

  loading = true;
  overview: CatalogOverview | null = null;
  allTables: TableCatalogEntry[] = [];
  filteredTables: TableCatalogEntry[] = [];
  searchText = '';
  selectedDomain: string | null = null;
  domainOptions: string[] = [];

  storagePieOptions: EChartsOption | null = null;
  domainBarOptions: EChartsOption | null = null;
  graphCatalog: GraphCatalogOverview | null = null;
  businessOverview: BusinessOverview | null = null;

  private domainColors: Record<string, string> = {
    bars: 'blue', security: 'green', taxonomy: 'orange',
    financial: 'gold', strategy: 'purple', kg: 'magenta',
    market_activity: 'cyan', other: 'default'
  };

  ngOnInit() {
    this.refresh(false);
  }

  ngOnDestroy() {
  }

  refresh(force: boolean) {
    this.loading = true;
    this.service.getCatalogOverview(force).subscribe({
      next: (ov) => {
        this.overview = ov;
        this.buildCharts();
      },
      error: () => {}
    });
    this.service.getCatalogTables(undefined, force).subscribe({
      next: (res) => {
        this.allTables = res.tables || [];
        this.domainOptions = [...new Set(this.allTables.map(t => t.domain))].sort();
        this.filterTables();
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
    this.service.getGraphCatalog().subscribe({
      next: (g) => { this.graphCatalog = g; },
      error: () => { this.graphCatalog = { available: false, total_nodes: 0, total_edges: 0 }; }
    });
    this.service.getBusinessOverview().subscribe({
      next: (b) => { this.businessOverview = b; },
      error: () => {}
    });
  }

  filterTables() {
    let tables = this.allTables;
    if (this.selectedDomain) {
      tables = tables.filter(t => t.domain === this.selectedDomain);
    }
    if (this.searchText) {
      const q = this.searchText.toLowerCase();
      tables = tables.filter(t =>
        t.table_name.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q)
      );
    }
    this.filteredTables = tables;
  }

  goToDetail(t: TableCatalogEntry) {
    this.router.navigate(['/phoenixa/catalog', t.schema, t.table_name]);
  }

  goToDetailByName(tableName: string) {
    const t = this.allTables.find(tbl => tbl.table_name === tableName);
    if (t) {
      this.router.navigate(['/phoenixa/catalog', t.schema, t.table_name]);
    }
  }

  getDomainColor(domain: string): string {
    return this.domainColors[domain] || 'default';
  }

  formatRows(n: number): string {
    if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return String(n);
  }

  private buildCharts() {
    if (!this.overview) return;

    // Storage pie chart
    const tiers = this.overview.storage_tiers;
    const pieData = Object.entries(tiers).map(([tier, info]) => ({
      name: tier === 'hot' ? '🔥 NVMe (Hot)' : '❄️ SATA (Warm)',
      value: info.disk_size_bytes
    }));
    this.storagePieOptions = {
      tooltip: {
        trigger: 'item',
        formatter: (p: any) => `${p.name}: ${this.humanSize(p.value)} (${p.percent}%)`
      },
      color: ['#ff7a45', '#36cfc9'],
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: true,
        label: { show: true, formatter: '{b}\n{d}%' },
        data: pieData
      }]
    };

    // Domain bar chart
    const domains = this.overview.domains;
    this.domainBarOptions = {
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'value',
        axisLabel: { formatter: (v: number) => this.humanSize(v) }
      },
      yAxis: {
        type: 'category',
        data: domains.map(d => d.domain),
        inverse: true
      },
      series: [{
        type: 'bar',
        data: domains.map(d => ({
          value: d.total_disk_size_bytes,
          itemStyle: { color: this.getDomainChartColor(d.domain) }
        })),
        label: {
          show: true,
          position: 'right',
          formatter: (p: any) => this.humanSize(p.value)
        }
      }]
    };
  }

  private humanSize(bytes: number): string {
    if (bytes >= 1099511627776) return (bytes / 1099511627776).toFixed(1) + ' TB';
    if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + ' GB';
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
    if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return bytes + ' B';
  }

  private getDomainChartColor(domain: string): string {
    const map: Record<string, string> = {
      bars: '#1890ff', security: '#52c41a', taxonomy: '#fa8c16',
      financial: '#faad14', strategy: '#722ed1', kg: '#eb2f96',
      market_activity: '#13c2c2', other: '#8c8c8c'
    };
    return map[domain] || '#8c8c8c';
  }
}



