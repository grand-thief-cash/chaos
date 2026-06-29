import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { ArtemisBiService } from '../services/artemis-bi.service';
import { BISymbolCoverageResponse, BIDatasetEntry, BICoverageDataset } from '../models/bi.models';

@Component({
  selector: 'app-bi-company-overview-page',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzButtonModule, NzSpinModule, NzTagModule, NzEmptyModule],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <!-- Company metadata placeholder -->
      <nz-card nzTitle="公司元数据" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="display: flex; gap: 24px; align-items: center; margin-bottom: 12px;">
          <div style="font-size: 24px; font-weight: 600;">{{ symbol }}</div>
          <nz-tag nzColor="blue">{{ market }}</nz-tag>
        </div>
        <nz-empty nzNotFoundContent="暂无公司元数据（证券信息/公司简介），待后续接入"></nz-empty>
      </nz-card>

      <!-- Available datasets with coverage -->
      <nz-card nzTitle="当前可用数据" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        @if (loading) {
          <nz-spin nzTip="加载中..."></nz-spin>
        } @else if (coverage) {
          <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 16px;">
            @for (ds of coverage.datasets; track ds.dataset) {
              <nz-card [nzTitle]="getDatasetLabel(ds.dataset)" nzSize="small" style="box-shadow: 0 1px 2px rgba(0,0,0,0.06);">
                @for (dt of ds.data_types; track dt.data_type) {
                  <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                      <span style="font-weight: 500;">{{ dt.data_type }}</span>
                      <nz-tag nzColor="geekblue">{{ dt.total_rows }} 行</nz-tag>
                    </div>
                    @if (dt.latest_period) {
                      <div style="font-size: 12px; color: #8c8c8c;">
                        时间范围: {{ dt.earliest_period }} ~ {{ dt.latest_period }}
                      </div>
                    }
                    @if (dt.by_report_type && dt.by_report_type.length > 0) {
                      <div style="margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px;">
                        @for (rt of dt.by_report_type; track rt.report_type) {
                          <nz-tag [nzColor]="reportTypeColor(rt.report_type)">
                            {{ reportTypeLabel(rt.report_type) }}: {{ rt.row_count }}
                          </nz-tag>
                        }
                      </div>
                    }
                    <button nz-button nzSize="small" nzType="link" style="padding: 0; margin-top: 6px;"
                            (click)="enterRaw(ds.dataset, dt.data_type)">
                      查看原始数据 →
                    </button>
                  </div>
                }
              </nz-card>
            }
          </div>
          @if (coverage.datasets.length === 0) {
            <nz-empty nzNotFoundContent="该公司暂无可用数据"></nz-empty>
          }
        } @else {
          <nz-empty nzNotFoundContent="无法加载数据"></nz-empty>
        }
      </nz-card>
    </div>
  `,
})
export class CompanyOverviewPageComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(ArtemisBiService);

  symbol = '';
  market = 'zh_a';
  loading = false;
  coverage: BISymbolCoverageResponse | null = null;
  datasets: BIDatasetEntry[] = [];

  ngOnInit(): void {
    this.symbol = this.route.snapshot.paramMap.get('symbol') || '';
    this.market = this.route.snapshot.queryParamMap.get('market') || 'zh_a';
    if (this.symbol) {
      this.loadCoverage();
    }
  }

  enterRaw(dataset: string, dataType: string): void {
    this.router.navigate(['/bi/company', this.symbol, 'raw', dataset, dataType], {
      queryParams: { market: this.market },
    });
  }

  getDatasetLabel(dataset: string): string {
    const found = this.datasets.find((d) => d.dataset === dataset);
    return found ? found.label_zh : dataset;
  }

  reportTypeLabel(rt: string): string {
    const map: Record<string, string> = { '1': '一季报', '2': '半年报', '3': '三季报', '4': '年报' };
    return map[rt] || rt;
  }

  reportTypeColor(rt: string): string {
    const map: Record<string, string> = { '1': 'cyan', '2': 'blue', '3': 'cyan', '4': 'purple' };
    return map[rt] || 'default';
  }

  private loadCoverage(): void {
    this.loading = true;
    this.api.getDatasets().subscribe({
      next: (resp) => {
        this.datasets = resp.datasets;
      },
      error: () => {
        this.datasets = [];
      },
    });
    this.api.getSymbolCoverage(this.symbol, this.market).subscribe({
      next: (resp) => {
        this.coverage = resp;
        this.loading = false;
      },
      error: () => {
        this.coverage = null;
        this.loading = false;
      },
    });
  }
}
