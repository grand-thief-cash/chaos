import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { first } from 'rxjs';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzAlertModule } from 'ng-zorro-antd/alert';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { CompanyContextBarComponent } from '../ui/company-context-bar.component';
import { BiApiService } from '../services/bi-api.service';
import { BIInsightResponse } from '../models/bi.models';

@Component({
  selector: 'app-financial-insight-page',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzAlertModule, NzSpinModule, NzEmptyModule, NzButtonModule, CompanyContextBarComponent],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      @if (loading) {
        <nz-spin nzTip="Loading insight..."></nz-spin>
      } @else if (errorMessage) {
        <nz-alert nzType="error" [nzMessage]="'加载失败'" [nzDescription]="errorMessage" nzShowIcon></nz-alert>
        <button nz-button (click)="goBack()">返回</button>
      } @else if (data) {
        <app-company-context-bar [company]="data.company" [asOfDate]="data.as_of_date" [latestPeriod]="data.latest_period"></app-company-context-bar>

        <nz-card nzTitle="结构化摘要" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <div style="font-size: 18px; font-weight: 600; color: #262626; margin-bottom: 8px;">{{ data.headline }}</div>
          <div style="display: flex; flex-direction: column; gap: 10px;">
            @for (item of data.structured_highlights; track item.code) {
              <div style="padding: 12px; border: 1px solid #f0f0f0; border-radius: 8px; background: #fafafa;">
                <div style="font-weight: 600;">{{ item.title }}</div>
                <div style="font-size: 13px; color: #595959; margin-top: 6px;">{{ item.message }}</div>
              </div>
            }
          </div>
        </nz-card>

        <nz-card nzTitle="异常与预警" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          @if (data.anomalies.length > 0) {
            <div style="display: flex; flex-direction: column; gap: 8px;">
              @for (item of data.anomalies; track item.code) {
                <nz-alert [nzType]="item.severity === 'high' ? 'error' : item.severity === 'medium' ? 'warning' : 'info'" [nzMessage]="item.title" [nzDescription]="item.message" nzShowIcon></nz-alert>
              }
            </div>
          } @else {
            <nz-empty nzNotFoundContent="当前无异常摘要"></nz-empty>
          }
        </nz-card>

        <nz-card nzTitle="趋势摘要" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <ul style="margin: 0; padding-left: 18px; line-height: 1.9; color: #595959;">
            @for (line of data.trend_summary; track line) {
              <li>{{ line }}</li>
            }
          </ul>
        </nz-card>
      } @else {
        <nz-empty nzNotFoundContent="No insight data"></nz-empty>
      }
    </div>
  `,
})
export class FinancialInsightPageComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(BiApiService);
  loading = false;
  data: BIInsightResponse | null = null;
  errorMessage: string | null = null;

  ngOnInit(): void {
    // Get symbol from parent route (the :symbol parameter in /bi/financial/company/:symbol)
    this.route.parent?.paramMap.pipe(first()).subscribe((params) => {
      const symbol = params?.get('symbol') ?? this.route.snapshot.paramMap.get('symbol');

      if (!symbol) {
        this.router.navigate(['/bi/financial']);
        return;
      }

      const asOfDate = this.route.snapshot.queryParamMap.get('as_of_date') ?? new Date().toISOString().slice(0, 10);
      this.loading = true;
      this.api.getCompanyInsight(symbol, asOfDate).subscribe({
        next: (resp) => {
          this.data = resp;
          this.loading = false;
        },
        error: (err) => {
          this.loading = false;
          this.errorMessage = err?.error?.detail || err?.message || '加载数据失败，请稍后重试';
        },
      });
    });
  }

  goBack(): void {
    this.router.navigate(['/bi/financial']);
  }
}

