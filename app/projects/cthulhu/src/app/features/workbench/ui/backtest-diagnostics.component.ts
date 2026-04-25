import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzToolTipModule } from 'ng-zorro-antd/tooltip';
import { NzResizableModule, NzResizeEvent } from 'ng-zorro-antd/resizable';
import { BarDetailEvent } from '../models/workbench.model';

@Component({
  selector: 'app-backtest-bar-details',
  standalone: true,
  imports: [
    CommonModule,
    NzTableModule,
    NzButtonModule,
    NzCardModule,
    NzTagModule,
    NzEmptyModule,
    NzToolTipModule,
    NzResizableModule,
  ],
  template: `
    <nz-card nzTitle="Transaction Details" [nzExtra]="extraTpl">
      <ng-template #extraTpl>
        <button nz-button nzSize="small" (click)="exportCsv()" [disabled]="!barDetails?.length">
          Export CSV
        </button>
      </ng-template>

      @if (!barDetails?.length) {
        <nz-empty nzNotFoundContent="No transaction detail data. Enable detail recording in config and re-run."></nz-empty>
      } @else {
        <nz-table
          #diagTable
          [nzData]="barDetails!"
          [nzPageSize]="50"
          nzSize="small"
          [nzScroll]="{ x: totalWidth + 'px' }"
          nzShowSizeChanger
          [nzPageSizeOptions]="[20, 50, 100, 200]"
        >
          <thead>
            <tr>
              @for (col of columns; track col.key; let i = $index) {
                <th
                  nz-resizable
                  nzBounds="window"
                  [nzMinWidth]="col.minWidth"
                  [nzMaxWidth]="col.maxWidth"
                  (nzResize)="onResize($event, i)"
                  [nzWidth]="col.width + 'px'"
                >
                  {{ col.title }}
                  <nz-resize-handle nzDirection="right"><div class="resize-trigger"></div></nz-resize-handle>
                </th>
              }
            </tr>
          </thead>
          <tbody>
            @for (row of diagTable.data; track $index) {
              <tr>
                <td>{{ row.timestamp }}</td>
                <td>{{ row.close | number:'1.2-4' }}</td>
                <td>
                  <nz-tag [nzColor]="actionColor(row.action)">{{ actionLabel(row.action) }}</nz-tag>
                </td>
                <td style="white-space: normal; word-break: break-word;">{{ row.reason }}</td>
                <td>{{ row.position_size }}</td>
                <td>{{ row.position_price | number:'1.2-4' }}</td>
                <td>{{ row.portfolio_value | number:'1.2-2' }}</td>
                <td>{{ row.cash | number:'1.2-2' }}</td>
                <td [style.color]="row.unrealized_pnl >= 0 ? '#3f8600' : '#cf1322'">
                  {{ row.unrealized_pnl | number:'1.2-2' }}
                </td>
                <td [style.color]="row.unrealized_pnl_pct >= 0 ? '#3f8600' : '#cf1322'">
                  {{ row.unrealized_pnl_pct * 100 | number:'1.2-4' }}%
                </td>
                <td>
                  @if (row.indicators) {
                    <span nz-tooltip [nzTooltipTitle]="formatIndicators(row.indicators)">
                      {{ briefIndicators(row.indicators) }}
                    </span>
                  }
                </td>
              </tr>
            }
          </tbody>
        </nz-table>
      }
    </nz-card>
  `,
  styles: [`
    :host ::ng-deep .resize-trigger {
      width: 4px;
      height: 100%;
      cursor: col-resize;
      position: absolute;
      right: 0;
      top: 0;
    }
    :host ::ng-deep .nz-resizable-handle {
      width: 4px;
      right: 0;
    }
    :host ::ng-deep th.nz-resizable {
      position: relative;
    }
  `],
})
export class BacktestBarDetailsComponent {
  @Input() barDetails?: BarDetailEvent[];

  columns = [
    { key: 'time',       title: 'Time',        width: 160, minWidth: 100, maxWidth: 300 },
    { key: 'close',      title: 'Close',       width: 90,  minWidth: 60,  maxWidth: 150 },
    { key: 'action',     title: 'Action',      width: 120, minWidth: 80,  maxWidth: 200 },
    { key: 'reason',     title: 'Reason',      width: 320, minWidth: 150, maxWidth: 800 },
    { key: 'position',   title: 'Position',    width: 80,  minWidth: 50,  maxWidth: 150 },
    { key: 'pos_price',  title: 'Pos Price',   width: 90,  minWidth: 60,  maxWidth: 150 },
    { key: 'portfolio',  title: 'Portfolio',   width: 110, minWidth: 70,  maxWidth: 200 },
    { key: 'cash',       title: 'Cash',        width: 100, minWidth: 60,  maxWidth: 200 },
    { key: 'pnl',        title: 'Unreal PnL',  width: 100, minWidth: 60,  maxWidth: 200 },
    { key: 'pnl_pct',    title: 'Unreal PnL%', width: 100, minWidth: 60,  maxWidth: 200 },
    { key: 'indicators', title: 'Indicators',  width: 200, minWidth: 80,  maxWidth: 600 },
  ];

  get totalWidth(): number {
    return this.columns.reduce((sum, c) => sum + c.width, 0);
  }

  onResize({ width }: NzResizeEvent, colIdx: number): void {
    this.columns[colIdx].width = width!;
  }

  actionColor(action: string): string {
    if (action.startsWith('ORDER_') && action.endsWith('_OK')) return action.includes('BUY') ? 'green' : 'red';
    switch (action) {
      case 'BUY': return 'green';
      case 'SELL': return 'red';
      case 'ORDER_FAILED': return 'magenta';
      case 'HOLD': return 'default';
      case 'SKIP': return 'orange';
      default: return 'default';
    }
  }

  actionLabel(action: string): string {
    const labels: Record<string, string> = {
      'ORDER_BUY_OK': '✓ BUY',
      'ORDER_SELL_OK': '✓ SELL',
      'ORDER_FAILED': '✗ FAIL',
    };
    return labels[action] || action;
  }

  briefIndicators(indicators: Record<string, any>): string {
    const entries = Object.entries(indicators)
      .filter(([, v]) => typeof v === 'number')
      .slice(0, 3)
      .map(([k, v]) => `${k}=${v}`);
    return entries.join(', ') + (Object.keys(indicators).length > 3 ? '...' : '');
  }

  formatIndicators(indicators: Record<string, any>): string {
    return Object.entries(indicators)
      .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
      .join('\n');
  }

  exportCsv(): void {
    if (!this.barDetails?.length) return;

    const headers = [
      'timestamp', 'close', 'action', 'reason',
      'position_size', 'position_price', 'portfolio_value', 'cash',
      'unrealized_pnl', 'unrealized_pnl_pct', 'indicators',
    ];

    const rows = this.barDetails.map(row => [
      row.timestamp,
      row.close,
      row.action,
      `"${(row.reason || '').replace(/"/g, '""')}"`,
      row.position_size,
      row.position_price,
      row.portfolio_value,
      row.cash,
      row.unrealized_pnl,
      row.unrealized_pnl_pct,
      row.indicators ? `"${JSON.stringify(row.indicators).replace(/"/g, '""')}"` : '',
    ]);

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bar_details_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }
}
