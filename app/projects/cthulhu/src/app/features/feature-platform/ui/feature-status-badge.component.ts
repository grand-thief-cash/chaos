import { Component, Input } from '@angular/core';
import { featureStatusTone } from '../models/feature-platform.utils';

@Component({
  selector: 'app-feature-status-badge',
  standalone: true,
  template: `<span class="status-badge" [class]="'status-badge tone-' + tone">{{ status || 'unknown' }}</span>`,
  styles: [`
    .status-badge {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 1px 8px;
      border: 1px solid transparent;
      border-radius: 999px;
      font: 700 11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
      letter-spacing: .035em;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .tone-success { color: #126346; background: #e7f7ef; border-color: #a7ddc5; }
    .tone-processing { color: #155b78; background: #e8f5fb; border-color: #9ed4e8; }
    .tone-warning { color: #8a4b08; background: #fff5df; border-color: #efc982; }
    .tone-danger { color: #9f2d2d; background: #fff0ed; border-color: #efb0a8; }
    .tone-unknown { color: #5f6570; background: #f0f1f3; border-color: #cdd0d5; border-style: dashed; }
    .tone-neutral { color: #394554; background: #eef2f5; border-color: #c7d0d8; }
  `],
})
export class FeatureStatusBadgeComponent {
  @Input() status = 'unknown';
  get tone() { return featureStatusTone(this.status); }
}
