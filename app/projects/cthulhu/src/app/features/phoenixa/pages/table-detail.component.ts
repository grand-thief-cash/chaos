import {Component, inject, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {ActivatedRoute, Router} from '@angular/router';
import {PhoenixAService} from '../services/phoenixa.service';
import {TableDetail, ColumnMeta} from '../models/phoenixa.models';
import {NzCardModule} from 'ng-zorro-antd/card';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzStatisticModule} from 'ng-zorro-antd/statistic';
import {NzGridModule} from 'ng-zorro-antd/grid';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzTagModule} from 'ng-zorro-antd/tag';
import {NzDescriptionsModule} from 'ng-zorro-antd/descriptions';
import {NzSpinModule} from 'ng-zorro-antd/spin';
import {NzIconModule} from 'ng-zorro-antd/icon';
import {NzCollapseModule} from 'ng-zorro-antd/collapse';
import {NzBadgeModule} from 'ng-zorro-antd/badge';

@Component({
  selector: 'app-table-detail',
  standalone: true,
  imports: [
    CommonModule,
    NzCardModule,
    NzTableModule,
    NzStatisticModule,
    NzGridModule,
    NzButtonModule,
    NzTagModule,
    NzDescriptionsModule,
    NzSpinModule,
    NzIconModule,
    NzCollapseModule,
    NzBadgeModule
  ],
  template: `
    <nz-spin [nzSpinning]="loading">

      <!-- Back button + title -->
      <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
        <button nz-button (click)="goBack()">
          <span nz-icon nzType="arrow-left"></span> Back
        </button>
        <h3 style="margin: 0;">
          <code>{{ detail?.schema }}.{{ detail?.table_name }}</code>
        </h3>
        <nz-tag *ngIf="detail?.storage_tier === 'hot'" nzColor="volcano">🔥 Hot (NVMe)</nz-tag>
        <nz-tag *ngIf="detail?.storage_tier === 'warm'" nzColor="cyan">❄️ Warm (SATA)</nz-tag>
        <nz-tag *ngIf="detail?.is_hypertable" nzColor="blue">TimescaleDB</nz-tag>
      </div>

      @if (detail) {
        <!-- Summary -->
        <nz-card nzTitle="概览" style="margin-bottom: 16px;">
          <nz-descriptions nzBordered [nzColumn]="3">
            <nz-descriptions-item nzTitle="Domain">
              <nz-tag [nzColor]="getDomainColor(detail.domain)">{{ detail.domain }}</nz-tag>
            </nz-descriptions-item>
            <nz-descriptions-item nzTitle="Description">{{ detail.description }}</nz-descriptions-item>
            <nz-descriptions-item nzTitle="Tablespace">{{ detail.tablespace }}</nz-descriptions-item>
            <nz-descriptions-item nzTitle="Row Count">{{ formatRows(detail.row_count) }}</nz-descriptions-item>
            <nz-descriptions-item nzTitle="Data Size">{{ detail.disk_size }}</nz-descriptions-item>
            <nz-descriptions-item nzTitle="Index Size">{{ detail.index_size }}</nz-descriptions-item>
          </nz-descriptions>

          @if (detail.time_range) {
            <div style="margin-top: 12px; padding: 8px 12px; background: #f6ffed; border-radius: 4px;">
              <strong>Time Range:</strong>
              <code>{{ detail.time_range.column }}</code> :
              {{ detail.time_range.min }} ~ {{ detail.time_range.max }}
            </div>
          }
        </nz-card>

        <!-- Columns -->
        <nz-card nzTitle="列信息" [nzExtra]="colCountTpl" style="margin-bottom: 16px;">
          <ng-template #colCountTpl>
            <nz-badge [nzCount]="detail.columns.length || 0" [nzOverflowCount]="999"
                      [nzStyle]="{backgroundColor: '#1890ff'}"></nz-badge>
          </ng-template>
          <nz-table #colTable [nzData]="detail.columns || []" nzSize="small" [nzShowPagination]="false">
            <thead>
              <tr>
                <th nzWidth="200px">Column</th>
                <th nzWidth="180px">Type</th>
                <th nzWidth="60px">Nullable</th>
                <th nzWidth="60px">PK</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let col of colTable.data">
                <td><code>{{ col.name }}</code></td>
                <td>
                  <nz-tag [nzColor]="getTypeColor(col.type)">{{ col.type }}</nz-tag>
                </td>
                <td nzAlign="center">{{ col.nullable ? '✓' : '✗' }}</td>
                <td nzAlign="center">{{ col.is_primary_key ? '🔑' : '' }}</td>
                <td style="color: #666;">{{ col.description || '—' }}</td>
              </tr>
            </tbody>
          </nz-table>
        </nz-card>

        <!-- JSONB Keys -->
        @if (jsonbColumns.length > 0) {
          <nz-card nzTitle="JSONB 字段详情" [nzExtra]="jsonbExtra" style="margin-bottom: 16px;">
            <ng-template #jsonbExtra>
              <span style="color: #999; font-size: 12px;">点击展开查看各字段的类型和样例数据</span>
            </ng-template>
            <nz-collapse>
              <nz-collapse-panel *ngFor="let col of jsonbColumns"
                                 [nzHeader]="col.name + ' (' + getJsonbKeyCount(col.jsonb_keys) + ' keys)'"
                                 [nzActive]="true">
                <!-- Type-based discovery: { type: [field, ...] } -->
                @if (isRecord(col.jsonb_keys)) {
                  @for (entry of getRecordEntries(col.jsonb_keys); track entry[0]) {
                    <div style="margin-bottom: 12px;">
                      <nz-tag nzColor="blue">{{ entry[0] }}</nz-tag>
                      <span style="color: #999; font-size: 12px; margin-left: 4px;">{{ entry[1].length }} fields</span>
                      <div style="margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px;">
                        <nz-tag *ngFor="let key of entry[1]" nzColor="geekblue">{{ key }}</nz-tag>
                      </div>
                    </div>
                  }
                }
                <!-- Generic discovery: [{ name, value_type, sample_vals }] -->
                @if (isObjectArray(col.jsonb_keys)) {
                  <nz-table #jsonbTable [nzData]="col.jsonb_keys" nzSize="small"
                            [nzPageSize]="50" [nzShowPagination]="col.jsonb_keys.length > 50"
                            [nzShowSizeChanger]="false">
                    <thead>
                      <tr>
                        <th nzWidth="220px">Field Name</th>
                        <th nzWidth="100px">Type</th>
                        <th>Sample Values</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr *ngFor="let k of jsonbTable.data">
                        <td><code>{{ k.name }}</code></td>
                        <td>
                          <nz-tag [nzColor]="getValueTypeColor(k.value_type)">{{ k.value_type }}</nz-tag>
                        </td>
                        <td style="font-size: 12px; color: #666;">
                          @if (k.sample_vals && k.sample_vals.length > 0) {
                            <span>{{ k.sample_vals.join(', ') }}</span>
                          } @else {
                            <span>—</span>
                          }
                        </td>
                      </tr>
                    </tbody>
                  </nz-table>
                }
                <!-- Simple string array fallback -->
                @if (isArray(col.jsonb_keys) && !isObjectArray(col.jsonb_keys)) {
                  <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                    <nz-tag *ngFor="let key of col.jsonb_keys" nzColor="geekblue">{{ key }}</nz-tag>
                  </div>
                }
              </nz-collapse-panel>
            </nz-collapse>
          </nz-card>
        }

        <!-- Indexes -->
        @if (detail.indexes && detail.indexes.length > 0) {
          <nz-card nzTitle="索引信息" style="margin-bottom: 16px;">
            <nz-table #idxTable [nzData]="detail.indexes" nzSize="small" [nzShowPagination]="false">
              <thead>
                <tr>
                  <th nzWidth="250px">Index Name</th>
                  <th>Columns</th>
                  <th nzWidth="80px">Unique</th>
                  <th nzWidth="80px">Type</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let idx of idxTable.data">
                  <td><code>{{ idx.name }}</code></td>
                  <td>
                    <nz-tag *ngFor="let c of idx.columns">{{ c }}</nz-tag>
                  </td>
                  <td nzAlign="center">{{ idx.is_unique ? '✓' : '' }}</td>
                  <td>
                    <nz-tag [nzColor]="idx.type === 'gin' ? 'purple' : 'default'">
                      {{ idx.type || 'btree' }}
                    </nz-tag>
                  </td>
                </tr>
              </tbody>
            </nz-table>
          </nz-card>
        }

        <!-- Data Lineage -->
        @if (detail.data_lineage) {
          <nz-card nzTitle="数据血缘">
            <nz-descriptions nzBordered [nzColumn]="2">
              <nz-descriptions-item nzTitle="Source System">
                <nz-tag nzColor="green">{{ detail.data_lineage.source_system }}</nz-tag>
              </nz-descriptions-item>
              <nz-descriptions-item nzTitle="Ingestion Method">
                {{ detail.data_lineage.ingestion_method || '—' }}
              </nz-descriptions-item>
              <nz-descriptions-item nzTitle="Refresh Schedule">
                {{ detail.data_lineage.refresh_schedule || '—' }}
              </nz-descriptions-item>
              <nz-descriptions-item nzTitle="API Endpoint">
                @if (detail.data_lineage.api_endpoint) {
                  <code>{{ detail.data_lineage.api_endpoint }}</code>
                } @else {
                  —
                }
              </nz-descriptions-item>
            </nz-descriptions>
          </nz-card>
        }

        <!-- Business Data -->
        @if (detail.api_endpoints?.length || detail.example_calls?.length || detail.related_tables?.length) {
          <nz-card nzTitle="\u4E1A\u52A1\u6570\u636E" style="margin-top: 16px;">
            @if (detail.api_endpoints?.length) {
              <div style="margin-bottom: 16px;">
                <h4 style="margin-bottom: 8px;">API \u7AEF\u70B9</h4>
                <nz-table [nzData]="detail.api_endpoints || []" nzSize="small" [nzShowPagination]="false">
                  <thead><tr>
                    <th nzWidth="60px">Method</th>
                    <th nzWidth="300px">Path</th>
                    <th>Description</th>
                  </tr></thead>
                  <tbody>
                    <tr *ngFor="let ep of detail.api_endpoints">
                      <td><nz-tag [nzColor]="ep.method === 'GET' ? 'blue' : 'green'">{{ ep.method }}</nz-tag></td>
                      <td><code>{{ ep.path }}</code></td>
                      <td>{{ ep.description }}</td>
                    </tr>
                  </tbody>
                </nz-table>
              </div>
            }
            @if (detail.example_calls?.length) {
              <div style="margin-bottom: 16px;">
                <h4 style="margin-bottom: 8px;">\u793A\u4F8B\u8C03\u7528</h4>
                @for (ex of detail.example_calls; track ex.title) {
                  <div style="margin: 4px 0;">
                    <span style="color: #666; margin-right: 4px;">{{ ex.title }}:</span>
                    <code style="background: #f0f5ff; padding: 2px 6px; border-radius: 3px;">{{ ex.url }}</code>
                  </div>
                }
              </div>
            }
            @if (detail.related_tables?.length) {
              <div style="margin-bottom: 16px;">
                <h4 style="margin-bottom: 8px;">\u5173\u8054\u8868</h4>
                <nz-table [nzData]="detail.related_tables || []" nzSize="small" [nzShowPagination]="false">
                  <thead><tr>
                    <th>\u5173\u8054\u8868</th>
                    <th>\u5173\u8054\u952E</th>
                    <th>\u8BF4\u660E</th>
                  </tr></thead>
                  <tbody>
                    <tr *ngFor="let cr of detail.related_tables">
                      <td><code style="cursor:pointer; color: #1890ff;" (click)="goToTable(cr.to_table)">{{ cr.to_table }}</code></td>
                      <td><code>{{ cr.join_key }}</code></td>
                      <td>{{ cr.description }}</td>
                    </tr>
                  </tbody>
                </nz-table>
              </div>
            }
            @if (detail.business_domain) {
              <div>
                <h4 style="margin-bottom: 8px;">\u6240\u5C5E\u57DF</h4>
                <nz-tag [nzColor]="getDomainColor(detail.business_domain.domain)">{{ detail.business_domain.label }}</nz-tag>
                <span style="color: #666; margin-left: 8px;">{{ detail.business_domain.description }}</span>
                <div style="margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px;">
                  @for (t of detail.business_domain.tables_in_domain; track t) {
                    <nz-tag nzColor="blue" style="cursor: pointer;" (click)="goToTable(t)">{{ t }}</nz-tag>
                  }
                </div>
              </div>
            }
          </nz-card>
        }
      }
    </nz-spin>
  `,
  styles: [`
    :host { display: block; padding: 16px; }
    code { font-size: 12px; background: #f5f5f5; padding: 2px 4px; border-radius: 3px; }
    h3 code { font-size: 16px; }
  `]
})
export class TableDetailComponent implements OnInit {
  private service = inject(PhoenixAService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  loading = true;
  detail: TableDetail | null = null;

  get jsonbColumns(): ColumnMeta[] {
    if (!this.detail?.columns) return [];
    return this.detail.columns.filter(c => c.jsonb_keys != null);
  }

  ngOnInit() {
    const schema = this.route.snapshot.paramMap.get('schema') || 'public';
    const table = this.route.snapshot.paramMap.get('table') || '';
    this.loadDetail(schema, table);
  }

  loadDetail(schema: string, table: string) {
    this.loading = true;
    this.service.getTableDetail(schema, table).subscribe({
      next: (d) => {
        this.detail = d;
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  goBack() {
    this.router.navigate(['/phoenixa/catalog']);
  }

  goToTable(tableName: string) {
    // Navigate to table detail — guess schema from current detail
    const schema = this.detail?.schema || 'security_dev';
    this.router.navigate(['/phoenixa/catalog', schema, tableName]);
  }

  getDomainColor(domain: string): string {
    const map: Record<string, string> = {
      bars: 'blue', security: 'green', taxonomy: 'orange',
      financial: 'gold', strategy: 'purple', kg: 'magenta',
      market_activity: 'cyan', other: 'default'
    };
    return map[domain] || 'default';
  }

  getTypeColor(type: string): string {
    if (type.includes('jsonb')) return 'purple';
    if (type.includes('int') || type.includes('decimal') || type.includes('numeric')) return 'blue';
    if (type.includes('varchar') || type.includes('text')) return 'green';
    if (type.includes('timestamp') || type.includes('date')) return 'orange';
    if (type.includes('bool')) return 'cyan';
    return 'default';
  }

  formatRows(n: number): string {
    if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return String(n);
  }

  isRecord(v: any): v is Record<string, string[]> {
    return v != null && typeof v === 'object' && !Array.isArray(v);
  }

  isArray(v: any): v is string[] {
    return Array.isArray(v);
  }

  isObjectArray(v: any): v is { name: string; value_type: string; sample_vals: string[] }[] {
    return Array.isArray(v) && v.length > 0 && typeof v[0] === 'object' && v[0] !== null && 'name' in v[0];
  }

  getRecordEntries(v: any): [string, string[]][] {
    if (!this.isRecord(v)) return [];
    return Object.entries(v) as [string, string[]][];
  }

  getJsonbKeyCount(v: any): number {
    if (this.isObjectArray(v)) return v.length;
    if (this.isArray(v)) return v.length;
    if (this.isRecord(v)) {
      let total = 0;
      for (const vals of Object.values(v)) total += (vals as string[]).length;
      return total;
    }
    return 0;
  }

  getValueTypeColor(type: string): string {
    switch (type) {
      case 'number': return 'blue';
      case 'string': return 'green';
      case 'boolean': return 'cyan';
      case 'object': return 'purple';
      case 'array': return 'orange';
      default: return 'default';
    }
  }
}

