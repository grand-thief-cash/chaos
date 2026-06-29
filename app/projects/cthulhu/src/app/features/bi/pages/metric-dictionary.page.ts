import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzTableModule } from 'ng-zorro-antd/table';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { BiApiService } from '../services/bi-api.service';
import { BIMetricDefinition } from '../models/bi-legacy.models';

@Component({
  selector: 'app-metric-dictionary-page',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzTableModule, NzTagModule, NzSpinModule],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <nz-card nzTitle="指标字典" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="color: #8c8c8c;">当前仅展示 BI MVP 指标，不包含 Atlas / narrative / insight 类指标。</div>
      </nz-card>

      <nz-card [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        @if (loading) {
          <nz-spin nzTip="Loading metrics..."></nz-spin>
        } @else {
          <nz-table #tbl [nzData]="metrics" nzSize="small" [nzFrontPagination]="false" [nzScroll]="{ x: '1200px' }">
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>分类</th>
                <th>展示类型</th>
                <th>公式</th>
                <th>字段来源</th>
                <th>Phase</th>
                <th>Available</th>
              </tr>
            </thead>
            <tbody>
              @for (item of tbl.data; track item.code) {
                <tr>
                  <td><code>{{ item.code }}</code></td>
                  <td>{{ item.label }}</td>
                  <td><nz-tag nzColor="blue">{{ item.category }}</nz-tag></td>
                  <td>{{ item.display_kind }}</td>
                  <td style="min-width: 260px; color: #595959;">{{ item.formula }}</td>
                  <td style="min-width: 260px; color: #595959;">{{ item.source_fields.join(', ') }}</td>
                  <td>{{ item.phase }}</td>
                  <td><nz-tag [nzColor]="item.available ? 'green' : 'red'">{{ item.available ? 'Yes' : 'No' }}</nz-tag></td>
                </tr>
              }
            </tbody>
          </nz-table>
        }
      </nz-card>
    </div>
  `,
})
export class MetricDictionaryPageComponent implements OnInit {
  private readonly api = inject(BiApiService);
  loading = false;
  metrics: BIMetricDefinition[] = [];

  ngOnInit(): void {
    this.loading = true;
    this.api.getMetricDefinitions().subscribe({
      next: (resp) => {
        this.metrics = resp.metrics;
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }
}

