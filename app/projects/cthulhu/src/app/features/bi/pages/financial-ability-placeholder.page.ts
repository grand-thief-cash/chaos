import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

@Component({
  selector: 'app-bi-financial-ability-placeholder-page',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="placeholder-page">
      <header>
        <h1>{{ title }}</h1>
        <span>财务能力分析</span>
      </header>
      <div class="placeholder-panel">
        <strong>{{ title }}页面待补充</strong>
        <p>当前先完成“盈利能力分析”的前端壳子和二级菜单结构，后续可以按同一套筛选、指标卡、趋势图和明细表继续补齐。</p>
        <a routerLink="/bi/financial-ability/profitability">返回盈利能力分析</a>
      </div>
    </section>
  `,
  styles: [`
    :host {
      display: block;
      min-height: calc(100vh - 110px);
      background: #eef4fb;
      color: #172033;
    }

    .placeholder-page {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    header,
    .placeholder-panel {
      background: #fff;
      border: 1px solid #dce7f2;
      padding: 20px;
    }

    h1 {
      margin: 0 0 6px;
      font-size: 26px;
      letter-spacing: 0;
    }

    header span,
    p {
      color: #667386;
    }

    .placeholder-panel {
      display: flex;
      flex-direction: column;
      gap: 12px;
      max-width: 680px;
    }

    .placeholder-panel strong {
      font-size: 18px;
    }
  `],
})
export class FinancialAbilityPlaceholderPageComponent {
  title = this.route.snapshot.data['title'] ?? '分析';

  constructor(private route: ActivatedRoute) {}
}
