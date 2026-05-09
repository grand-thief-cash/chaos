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
          <nz-card nzTitle="JSONB 字段详情" style="margin-bottom: 16px;">
            <nz-collapse>
              <nz-collapse-panel *ngFor="let col of jsonbColumns"
                                 [nzHeader]="col.name"
                                 [nzActive]="true">
                @if (isRecord(col.jsonb_keys)) {
                  <div *ngFor="let entry of getRecordEntries(col.jsonb_keys)" style="margin-bottom: 12px;">
                    <strong>{{ entry[0] }}</strong>
                    <div style="margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px;">
                      <nz-tag *ngFor="let key of entry[1]" nzColor="geekblue">{{ key }}</nz-tag>
                    </div>
                  </div>
                } @else if (isArray(col.jsonb_keys)) {
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

  getDomainColor(domain: string): string {
    const map: Record<string, string> = {
      bars: 'blue', security: 'green', taxonomy: 'orange',
      financial: 'gold', strategy: 'purple', kg: 'magenta',
      factor: 'cyan', regime: 'red', other: 'default'
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

  getRecordEntries(v: any): [string, string[]][] {
    if (!this.isRecord(v)) return [];
    return Object.entries(v) as [string, string[]][];
  }
}

