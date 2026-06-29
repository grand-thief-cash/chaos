import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzCardModule } from 'ng-zorro-antd/card';
import { NzTagModule } from 'ng-zorro-antd/tag';
import { BICompanyMeta } from '../models/bi-legacy.models';

@Component({
  selector: 'app-company-context-bar',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzTagModule],
  template: `
    <nz-card nzSize="small" [nzBordered]="false" style="box-shadow: 0 1px 4px rgba(0,0,0,0.08);">
      <div style="display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap;">
        <div>
          <div style="font-size: 18px; font-weight: 600;">{{ company.name || company.symbol }}</div>
          <div style="margin-top: 6px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
            <nz-tag nzColor="blue">{{ company.symbol }}</nz-tag>
            <nz-tag nzColor="geekblue">{{ company.market }}</nz-tag>
            @if (company.exchange) { <nz-tag>{{ company.exchange }}</nz-tag> }
            @if (company.industry.name) { <nz-tag nzColor="purple">{{ company.industry.name }}</nz-tag> }
          </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(2, auto); gap: 8px 16px; font-size: 12px; color: #595959;">
          <div>As Of: <strong>{{ asOfDate }}</strong></div>
          <div>Latest Period: <strong>{{ latestPeriod }}</strong></div>
          <div>Comp Type: <strong>{{ company.comp_type_code }}</strong></div>
          <div>Financial Sector: <strong>{{ company.financial_sector ? 'Yes' : 'No' }}</strong></div>
        </div>
      </div>
    </nz-card>
  `,
})
export class CompanyContextBarComponent {
  @Input({ required: true }) company!: BICompanyMeta;
  @Input() asOfDate: string = '';
  @Input() latestPeriod: string = '';
}



