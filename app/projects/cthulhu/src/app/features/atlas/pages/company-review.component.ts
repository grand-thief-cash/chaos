import {CommonModule} from '@angular/common';
import {Component, inject} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {AtlasApiService} from '../services/atlas-api.service';

@Component({
  selector: 'app-atlas-company-review',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <h1>Company industry review</h1>
      <p>
        The review separates observed facts and disclosures from analyst views,
        forecasts, and management plans. It uses only governed Atlas query tools.
      </p>
      <div>
        <input [(ngModel)]="companyName" placeholder="Company name or alias">
        <button (click)="run()" [disabled]="!companyName.trim() || loading">
          {{loading ? 'Generating…' : 'Generate review'}}
        </button>
      </div>
      <p class="error" *ngIf="error">{{error}}</p>
      <article *ngIf="result">
        <div class="answer">{{result.answer}}</div>
        <h2>Evidence references</h2>
        <pre>{{result.citations | json}}</pre>
        <details>
          <summary>Tool trace</summary>
          <pre>{{result.tool_trace | json}}</pre>
        </details>
      </article>
    </section>
  `,
  styles: [`
    .page{padding:24px}input{width:min(520px,70%);padding:8px}
    button{margin-left:8px;padding:8px 14px}.answer{white-space:pre-wrap;line-height:1.65}
    article{margin-top:18px;border:1px solid #ddd;border-radius:6px;padding:16px}
    pre{background:#fafafa;padding:12px;overflow:auto}.error{color:#c62828}
  `],
})
export class CompanyReviewComponent {
  private api = inject(AtlasApiService);
  companyName = '';
  loading = false;
  error = '';
  result: any;

  run(): void {
    this.loading = true;
    this.error = '';
    this.api.companyReview(this.companyName.trim()).subscribe({
      next: result => {
        this.result = result;
        this.loading = false;
      },
      error: error => {
        this.error = error.message;
        this.loading = false;
      },
    });
  }
}
