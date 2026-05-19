import { Component, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzButtonModule } from 'ng-zorro-antd/button';

@Component({
  selector: 'app-company-financial-shell',
  standalone: true,
  imports: [CommonModule, FormsModule, NzInputModule, RouterOutlet, RouterLink, RouterLinkActive, NzButtonModule],
  template: `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
        <div>
          <div style="font-size: 20px; font-weight: 600;">公司财务看板</div>
          <div style="color: #8c8c8c; font-size: 12px; margin-top: 4px;">当前聚焦 BI 结构化财务看板，不含 Atlas / narrative 集成</div>
        </div>
        <div style="display: flex; gap: 12px; align-items: end; flex-wrap: wrap;">
          <div style="font-size: 12px; color: #595959;">Symbol: <strong>{{ symbol() }}</strong></div>
          <div>
            <label style="display: block; font-size: 12px; color: #595959; margin-bottom: 4px;">As Of Date</label>
            <input nz-input type="date" [ngModel]="asOfDate()" (ngModelChange)="asOfDateValue = $event" style="width: 180px;" />
          </div>
        </div>
      </div>

      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
        <a nz-button nzSize="small" [routerLink]="['overview']" [queryParams]="queryParams" routerLinkActive="ant-btn-primary" [routerLinkActiveOptions]="{ exact: true }">总览</a>
        <a nz-button nzSize="small" [routerLink]="['dupont']" [queryParams]="queryParams" routerLinkActive="ant-btn-primary">杜邦</a>
        <a nz-button nzSize="small" [routerLink]="['quality']" [queryParams]="queryParams" routerLinkActive="ant-btn-primary">质量</a>
        <a nz-button nzSize="small" [routerLink]="['insight']" [queryParams]="queryParams" routerLinkActive="ant-btn-primary">摘要</a>
      </div>

      <router-outlet></router-outlet>
    </div>
  `,
})
export class CompanyFinancialShellPageComponent {
  private readonly route = inject(ActivatedRoute);
  readonly symbol = computed(() => this.route.snapshot.paramMap.get('symbol') ?? '');
  asOfDateValue = this.route.snapshot.queryParamMap.get('as_of_date') ?? new Date().toISOString().slice(0, 10);

  readonly asOfDate = computed(() => this.asOfDateValue);

  get queryParams(): Record<string, string> {
    return { as_of_date: this.asOfDateValue };
  }
}



