import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzButtonModule } from 'ng-zorro-antd/button';

@Component({
  selector: 'app-bi-trend-controls',
  standalone: true,
  imports: [CommonModule, NzButtonModule],
  template: `
    <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 16px;">
      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-size: 12px; color: #595959;">时间维度</span>
        <button nz-button nzSize="small" [nzType]="viewMode === 'quarterly' ? 'primary' : 'default'" (click)="setViewMode('quarterly')">季度</button>
        <button nz-button nzSize="small" [nzType]="viewMode === 'annual' ? 'primary' : 'default'" (click)="setViewMode('annual')">年度</button>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <span style="font-size: 12px; color: #595959;">趋势期数</span>
        @for (limit of periodOptions; track limit) {
          <button nz-button nzSize="small" [nzType]="periodLimit === limit ? 'primary' : 'default'" (click)="setPeriodLimit(limit)">{{ limit }}</button>
        }
      </div>
    </div>
  `,
})
export class TrendControlsComponent {
  @Input() periodLimit: 12 | 16 | 20 = 12;
  @Input() viewMode: 'quarterly' | 'annual' = 'quarterly';

  @Output() periodLimitChange = new EventEmitter<12 | 16 | 20>();
  @Output() viewModeChange = new EventEmitter<'quarterly' | 'annual'>();

  readonly periodOptions: Array<12 | 16 | 20> = [12, 16, 20];

  setPeriodLimit(limit: 12 | 16 | 20): void {
    if (this.periodLimit === limit) return;
    this.periodLimit = limit;
    this.periodLimitChange.emit(limit);
  }

  setViewMode(mode: 'quarterly' | 'annual'): void {
    if (this.viewMode === mode) return;
    this.viewMode = mode;
    this.viewModeChange.emit(mode);
  }
}

