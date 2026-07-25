import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzTableModule } from 'ng-zorro-antd/table';
import {
  FeaturePreviewResponse,
  FeatureScopeDraft,
  FeatureScopeRequest,
} from '../models/feature-platform.models';
import { featurePlatformError } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeaturePlatformStore } from '../state/feature-platform.store';
import { FeatureScopeEditorComponent } from '../ui/feature-scope-editor.component';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

interface PreviewDisplayRow {
  as_of_time: string;
  feature_code: string;
  version: number;
  security_id: number;
  value: number | null;
  value_status: string;
}

@Component({
  selector: 'app-feature-preview-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzButtonModule,
    NzEmptyModule,
    NzInputModule,
    NzSpinModule,
    NzTableModule,
    FeatureScopeEditorComponent,
    FeatureStatusBadgeComponent,
  ],
  template: `
    <div class="fp-page preview-layout">
      <section class="fp-panel">
        <div class="fp-panel-title">
          <div><div class="fp-eyebrow">Same kernel · no persistence sink</div><h2>Feature Preview</h2></div>
          <app-feature-status-badge status="not_persisted"></app-feature-status-badge>
        </div>
        <div class="fp-alert">
          Preview never creates Run, RunItem, Subject or Value rows. Results remain in browser memory and disappear on refresh.
        </div>
        <app-feature-scope-editor [draft]="draft" (draftChange)="updateDraft($event)"></app-feature-scope-editor>
        <div class="fp-field" style="margin-top:12px">
          <label>Declared preview overrides (JSON)</label>
          <textarea nz-input rows="3" [(ngModel)]="overridesText" (ngModelChange)="scopeChanged()" placeholder='{}'></textarea>
          <small class="fp-muted">Only keys declared by the selected manifest are accepted.</small>
        </div>
        @if (error) { <div class="fp-alert danger" style="margin-top:12px"><strong>{{ error.code }}</strong> {{ error.message }}</div> }
        <div class="fp-actions" style="margin-top:14px">
          <button nz-button (click)="resolve()" [nzLoading]="resolving">Resolve scope & cost</button>
          <button nz-button nzType="primary" (click)="runPreview()" [nzLoading]="previewing" [disabled]="!resolution?.allowed_for_preview">Run non-persisted Preview</button>
        </div>
      </section>

      <aside class="fp-panel scope-card">
        <div class="fp-eyebrow">Execution impact</div>
        <h3>Scope Summary</h3>
        @if (resolution; as resolved) {
          <div class="fp-dimension-grid">
            <div class="fp-dimension"><span>Securities</span>{{ resolved.scope.security_count }}</div>
            <div class="fp-dimension"><span>Evaluations</span>{{ resolved.scope.evaluation_count }}</div>
            <div class="fp-dimension"><span>DAG nodes</span>{{ resolved.scope.dag_node_count }}</div>
            <div class="fp-dimension"><span>Execution cells</span>{{ resolved.scope.estimated_execution_cells }}</div>
          </div>
          @for (warning of resolved.warnings; track warning) { <div class="fp-alert" style="margin-top:10px">{{ warning }}</div> }
          @for (violation of resolved.violations; track violation) { <div class="fp-alert danger" style="margin-top:10px">{{ violation }}</div> }
          <div class="fp-meta" style="margin-top:10px"><label>Universe hash</label><span class="fp-code">{{ resolved.scope.universe_hash }}</span></div>
        } @else {
          <nz-empty nzNotFoundContent="Resolve the scope before execution."></nz-empty>
        }
      </aside>

      @if (result; as preview) {
        <section class="fp-panel results">
          <div class="fp-panel-title">
            <div>
              <div class="fp-eyebrow">Ephemeral result · {{ preview.preview_id }}</div>
              <h2>Preview Values</h2>
            </div>
            <div class="fp-actions">
              <app-feature-status-badge [status]="preview.non_canonical ? 'non_canonical' : 'canonical'"></app-feature-status-badge>
              <button nz-button (click)="downloadJson()">JSON</button>
              <button nz-button (click)="downloadCsv()">CSV</button>
            </div>
          </div>
          <div class="quality-strip">
            <span><strong>{{ qualityTotal('valid') }}</strong> valid</span>
            <span><strong>{{ qualityTotal('missing') }}</strong> missing</span>
            <span><strong>{{ qualityTotal('invalid') }}</strong> invalid</span>
            <span><strong>{{ preview.evaluations.length }}</strong> evaluations</span>
          </div>
          <nz-spin [nzSpinning]="previewing">
            <nz-table #resultTable [nzData]="displayRows()" nzSize="small" [nzPageSize]="50" [nzShowSizeChanger]="true">
              <thead><tr><th>As-of</th><th>Feature</th><th>Security ID</th><th>Value</th><th>Status</th></tr></thead>
              <tbody>
                @for (row of resultTable.data; track row.as_of_time + ':' + row.feature_code + ':' + row.security_id) {
                  <tr>
                    <td>{{ row.as_of_time | date:'medium' }}</td>
                    <td class="fp-code">{{ row.feature_code }}&#64;{{ row.version }}</td>
                    <td class="fp-code">{{ row.security_id }}</td>
                    <td class="fp-code">{{ row.value ?? 'null' }}</td>
                    <td><app-feature-status-badge [status]="row.value_status"></app-feature-status-badge></td>
                  </tr>
                }
              </tbody>
            </nz-table>
          </nz-spin>
        </section>
      }
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
  styles: [`
    .preview-layout{grid-template-columns:minmax(0,1.35fr) minmax(270px,.65fr);align-items:start}
    .scope-card{position:sticky;top:12px}.results{grid-column:1/-1}
    .quality-strip{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
    .quality-strip span{padding:7px 10px;border:1px solid #d8d3c9;background:#faf8f3}
    @media(max-width:900px){.preview-layout{grid-template-columns:1fr}.scope-card{position:static}.results{grid-column:auto}}
  `],
})
export class PreviewPageComponent {
  private readonly api = inject(FeaturePlatformApiService);
  private readonly store = inject(FeaturePlatformStore);
  draft: FeatureScopeDraft = this.defaultDraft();
  overridesText = '{}';
  resolution: import('../models/feature-platform.models').FeatureScopeResolution | null = null;
  result: FeaturePreviewResponse | null = null;
  resolving = false;
  previewing = false;
  error: ReturnType<typeof featurePlatformError> | null = null;

  scopeChanged(): void {
    this.resolution = null;
    this.result = null;
  }

  updateDraft(draft: FeatureScopeDraft): void {
    this.draft = draft;
    this.scopeChanged();
  }

  resolve(): void {
    const request = this.request();
    if (!request) return;
    this.resolving = true;
    this.error = null;
    this.api.resolveScope(request).subscribe({
      next: (resolution) => {
        this.resolution = resolution;
        this.resolving = false;
      },
      error: (error) => {
        this.error = featurePlatformError(error);
        this.resolving = false;
      },
    });
  }

  runPreview(): void {
    const request = this.request();
    if (!request) return;
    let overrides: Record<string, unknown>;
    try {
      overrides = JSON.parse(this.overridesText || '{}');
      if (!overrides || Array.isArray(overrides) || typeof overrides !== 'object') throw new Error();
    } catch {
      this.error = { code: 'PREVIEW_OVERRIDE_INVALID', message: 'Preview overrides must be a JSON object.' };
      return;
    }
    this.previewing = true;
    this.error = null;
    this.result = null;
    this.api.preview({ ...request, preview_overrides: overrides }).subscribe({
      next: (result) => {
        this.result = result;
        this.previewing = false;
      },
      error: (error) => {
        this.error = featurePlatformError(error);
        this.previewing = false;
      },
    });
  }

  displayRows(): PreviewDisplayRow[] {
    return (this.result?.evaluations || []).flatMap((evaluation) =>
      evaluation.rows.map((row) => ({ ...row, as_of_time: evaluation.as_of_time })),
    );
  }

  qualityTotal(kind: 'valid' | 'missing' | 'invalid'): number {
    return (this.result?.evaluations || []).reduce(
      (total, evaluation) => total + evaluation.quality_summary[kind],
      0,
    );
  }

  downloadJson(): void {
    if (this.result) this.download('feature-preview.json', JSON.stringify(this.result, null, 2), 'application/json');
  }

  downloadCsv(): void {
    const header = 'as_of_time,feature_code,version,security_id,value,value_status';
    const lines = this.displayRows().map((row) => [
      row.as_of_time,
      row.feature_code,
      row.version,
      row.security_id,
      row.value ?? '',
      row.value_status,
    ].map((value) => JSON.stringify(value)).join(','));
    this.download('feature-preview.csv', [header, ...lines].join('\n'), 'text/csv;charset=utf-8');
  }

  private request(): FeatureScopeRequest | null {
    if (!this.draft.featureCode || !this.draft.version) {
      this.error = { code: 'FEATURE_REQUIRED', message: 'Choose a published Feature version.' };
      return null;
    }
    const securityIds = this.securityIds();
    if (this.draft.universeMode === 'explicit' && !securityIds.length) {
      this.error = { code: 'UNIVERSE_REQUIRED', message: 'Explicit universe requires positive Security IDs.' };
      return null;
    }
    const evaluation = this.draft.evaluationMode === 'point'
      ? { mode: 'point' as const, as_of_time: new Date(this.draft.asOf).toISOString() }
      : {
        mode: 'range' as const,
        start_as_of: new Date(this.draft.startAsOf).toISOString(),
        end_as_of: new Date(this.draft.endAsOf).toISOString(),
        step: this.draft.step,
      };
    return {
      feature_refs: [{ code: this.draft.featureCode, version: this.draft.version }],
      universe: { mode: this.draft.universeMode, security_ids: this.draft.universeMode === 'explicit' ? securityIds : [] },
      evaluation,
      data_cutoff_policy: this.draft.cutoffMode === 'same_as_as_of'
        ? { mode: 'same_as_as_of' }
        : { mode: 'lag_seconds', seconds: Number(this.draft.cutoffLagSeconds) },
      market: this.draft.market.trim(),
      source_profile: this.draft.sourceProfile.trim(),
    };
  }

  private securityIds(): number[] {
    const ids = this.draft.securityIdsText.split(/[\s,]+/).filter(Boolean).map(Number);
    return ids.every((id) => Number.isInteger(id) && id > 0) ? [...new Set(ids)] : [];
  }

  private download(filename: string, content: string, type: string): void {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  private defaultDraft(): FeatureScopeDraft {
    const now = new Date();
    const monthAgo = new Date(now);
    monthAgo.setMonth(monthAgo.getMonth() - 1);
    return {
      featureCode: '',
      version: null,
      universeMode: 'explicit',
      securityIdsText: '',
      evaluationMode: 'point',
      asOf: this.localDateTime(now),
      startAsOf: this.localDateTime(monthAgo),
      endAsOf: this.localDateTime(now),
      step: 'monthly',
      cutoffMode: 'same_as_as_of',
      cutoffLagSeconds: 0,
      market: 'zh_a',
      sourceProfile: this.store.sourceProfile(),
    };
  }

  private localDateTime(date: Date): string {
    return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
  }
}
