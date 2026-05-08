import {Component, inject, OnDestroy, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {PhoenixAService} from '../services/phoenixa.service';
import {BufferStats, WriteBufferStatus} from '../models/phoenixa.models';
import {NzCardModule} from 'ng-zorro-antd/card';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzBadgeModule} from 'ng-zorro-antd/badge';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzStatisticModule} from 'ng-zorro-antd/statistic';
import {NzGridModule} from 'ng-zorro-antd/grid';

@Component({
  selector: 'app-phoenixa-buffer-stats',
  standalone: true,
  imports: [
    CommonModule,
    NzCardModule,
    NzTableModule,
    NzBadgeModule,
    NzButtonModule,
    NzStatisticModule,
    NzGridModule
  ],
  template: `
    <nz-card nzTitle="Write Buffer Status" [nzExtra]="extraTpl">
      <ng-template #extraTpl>
        <nz-badge [nzStatus]="status?.enabled ? 'success' : 'default'"
                  [nzText]="status?.enabled ? 'Enabled' : 'Disabled'"></nz-badge>
        <button nz-button nzType="link" (click)="refresh()">Refresh</button>
      </ng-template>

      <!-- Summary row -->
      <div nz-row [nzGutter]="16" style="margin-bottom: 16px;">
        <div nz-col [nzSpan]="6">
          <nz-statistic [nzValue]="totalSubmitted" nzTitle="Total Submitted"></nz-statistic>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-statistic [nzValue]="totalFlushed" nzTitle="Total Flushed"></nz-statistic>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-statistic [nzValue]="totalPending" nzTitle="Pending Items"></nz-statistic>
        </div>
        <div nz-col [nzSpan]="6">
          <nz-statistic [nzValue]="activeBuffers" nzTitle="Active Buffers"></nz-statistic>
        </div>
      </div>

      <!-- Per-buffer table -->
      <nz-table #bufferTable [nzData]="buffers" [nzLoading]="loading"
                nzSize="small" [nzShowPagination]="false">
        <thead>
          <tr>
            <th>Buffer Key</th>
            <th nzAlign="right">Submitted</th>
            <th nzAlign="right">Flushed</th>
            <th nzAlign="right">Pending</th>
            <th nzAlign="right">Flush Count</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let buf of bufferTable.data">
            <td><code>{{ buf.key }}</code></td>
            <td nzAlign="right">{{ buf.submitted_rows | number }}</td>
            <td nzAlign="right">{{ buf.flushed_rows | number }}</td>
            <td nzAlign="right">
              <span [style.color]="buf.pending_items > 1000 ? '#ff4d4f' : 'inherit'">
                {{ buf.pending_items | number }}
              </span>
            </td>
            <td nzAlign="right">{{ buf.flush_count | number }}</td>
          </tr>
        </tbody>
      </nz-table>
    </nz-card>
  `
})
export class BufferStatsComponent implements OnInit, OnDestroy {
  private service = inject(PhoenixAService);
  private intervalId: any;

  status: WriteBufferStatus | null = null;
  buffers: BufferStats[] = [];
  loading = true;

  get totalSubmitted(): number {
    return this.buffers.reduce((s, b) => s + b.submitted_rows, 0);
  }
  get totalFlushed(): number {
    return this.buffers.reduce((s, b) => s + b.flushed_rows, 0);
  }
  get totalPending(): number {
    return this.buffers.reduce((s, b) => s + b.pending_items, 0);
  }
  get activeBuffers(): number {
    return this.buffers.length;
  }

  ngOnInit() {
    this.refresh();
    // Auto-refresh every 10s
    this.intervalId = setInterval(() => this.refresh(), 10000);
  }

  ngOnDestroy() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
    }
  }

  refresh() {
    this.loading = true;
    this.service.getBufferStats().subscribe({
      next: (res) => {
        this.status = res;
        this.buffers = res.buffers || [];
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      }
    });
  }
}

