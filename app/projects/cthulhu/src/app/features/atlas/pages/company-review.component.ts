import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzIconModule } from 'ng-zorro-antd/icon';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { NzDividerModule } from 'ng-zorro-antd/divider';
import { NzMessageService } from 'ng-zorro-antd/message';
import { AtlasApiService } from '../services/atlas-api.service';

@Component({
  selector: 'app-company-review',
  standalone: true,
  imports: [
    CommonModule, FormsModule, NzCardModule, NzInputModule, NzButtonModule,
    NzSpinModule, NzEmptyModule, NzIconModule, NzTagModule, NzDividerModule,
  ],
  template: `
    <div style="display: flex; flex-direction: column; gap: 12px;">
      <!-- Search -->
      <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
        <div style="display: flex; gap: 12px; align-items: center;">
          <input nz-input [(ngModel)]="companyName" nzSize="small" placeholder="Enter company name (normalized)..."
            style="max-width: 300px;" (keyup.enter)="search()" />
          <button nz-button nzType="primary" nzSize="small" [nzLoading]="loading" (click)="search()">
            <span nz-icon nzType="file-search"></span> Generate Review
          </button>
        </div>
      </nz-card>

      @if (loading) {
        <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <nz-spin nzTip="Generating review with LLM..." nzSimple
            style="display: flex; justify-content: center; padding: 80px;"></nz-spin>
        </nz-card>
      } @else if (review) {
        <!-- Graph data summary -->
        <nz-card nzSize="small" nzTitle="Graph Data Summary" [nzBordered]="false"
          style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <div style="display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px;">
            @if (review.graph_data?.relationships_count) {
              <div>
                <span style="color: #999;">Relationships:</span>
                <span style="font-weight: 500; margin-left: 4px;">{{ review.graph_data.relationships_count }}</span>
              </div>
            }
            @if (review.graph_data?.competitors_count) {
              <div>
                <span style="color: #999;">Competitors:</span>
                <span style="font-weight: 500; margin-left: 4px;">{{ review.graph_data.competitors_count }}</span>
              </div>
            }
            @if (review.graph_data?.events_count) {
              <div>
                <span style="color: #999;">Events:</span>
                <span style="font-weight: 500; margin-left: 4px;">{{ review.graph_data.events_count }}</span>
              </div>
            }
          </div>

          @if (review.graph_data?.risk_exposure?.resources?.length) {
            <nz-divider nzText="Resource Dependencies" nzOrientation="left" style="margin: 12px 0 8px;"></nz-divider>
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
              @for (r of review.graph_data.risk_exposure.resources; track r.resource) {
                <nz-tag>
                  {{ r.resource }}
                  @if (r.price_trend && r.price_trend !== 'unknown') {
                    <span [style.color]="r.price_trend === 'up' ? '#cf1322' : r.price_trend === 'down' ? '#389e0d' : '#999'">
                      {{ r.price_trend === 'up' ? '↑' : r.price_trend === 'down' ? '↓' : '→' }}
                    </span>
                  }
                </nz-tag>
              }
            </div>
          }
        </nz-card>

        <!-- Review text -->
        <nz-card nzSize="small" [nzTitle]="'Investment Review: ' + review.company" [nzBordered]="false"
          style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <div style="font-size: 13px; line-height: 1.8; white-space: pre-wrap; color: #333;">{{ review.review }}</div>
        </nz-card>
      } @else if (searched) {
        <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
          <nz-empty nzNotFoundContent="Company not found or no data available"></nz-empty>
        </nz-card>
      }
    </div>
  `,
})
export class CompanyReviewComponent {
  private api = inject(AtlasApiService);
  private msg = inject(NzMessageService);

  companyName = '';
  loading = false;
  searched = false;
  review: any = null;

  search(): void {
    if (!this.companyName.trim()) {
      this.msg.warning('Please enter a company name');
      return;
    }
    this.loading = true;
    this.searched = true;
    this.review = null;
    this.api.getCompanyReview(this.companyName.trim()).subscribe({
      next: (r) => { this.review = r; this.loading = false; },
      error: () => { this.msg.error('Failed to generate review'); this.loading = false; },
    });
  }
}


