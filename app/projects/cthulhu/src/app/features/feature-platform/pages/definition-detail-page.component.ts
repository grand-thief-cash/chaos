import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject, catchError, forkJoin, of, switchMap, takeUntil } from 'rxjs';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzCollapseModule } from 'ng-zorro-antd/collapse';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { NzTableModule } from 'ng-zorro-antd/table';
import { FeatureAvailability, FeatureDefinitionDetail, FeatureRun } from '../models/feature-platform.models';
import { featurePlatformError, unknownAvailability } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeaturePlatformStore } from '../state/feature-platform.store';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-definition-detail-page',
  standalone: true,
  imports: [CommonModule, RouterLink, NzButtonModule, NzCollapseModule, NzEmptyModule, NzSpinModule, NzTableModule, FeatureStatusBadgeComponent],
  template: `
    <div class="fp-page">
      @if (error) { <div class="fp-alert danger"><strong>{{ error.code }}</strong> {{ error.message }}</div> }
      <nz-spin [nzSpinning]="loading">
        @if (detail; as data) {
          <section class="fp-panel">
            <div class="fp-panel-title">
              <div><div class="fp-eyebrow">Feature definition</div><h2>{{ data.definition.display_name }}</h2><div class="fp-code">{{ data.definition.feature_code }}</div></div>
              <div class="fp-actions">
                <a nz-button [routerLink]="['../../lineage', data.definition.feature_code]">Lineage</a>
                <a nz-button [routerLink]="['../../runs']" [queryParams]="{ feature_version_id: availability?.latest_published_version_id }">Runs</a>
                <a nz-button [routerLink]="['../../values']" [queryParams]="{ feature_code: data.definition.feature_code, latest: true }">Values</a>
                <a nz-button nzType="primary" [routerLink]="['../../compute']" [queryParams]="{ feature_code: data.definition.feature_code, version: latestPublishedVersion() }">Compute</a>
              </div>
            </div>
            <p>{{ data.definition.description || 'No business description was supplied.' }}</p>
            <div class="fp-meta-grid">
              <div class="fp-meta"><label>Lifecycle</label><app-feature-status-badge [status]="data.definition.status"></app-feature-status-badge></div>
              <div class="fp-meta"><label>Kind / Entity / Value</label>{{ data.definition.kind }} · {{ data.definition.entity_type }} · {{ data.definition.value_type }}</div>
              <div class="fp-meta"><label>Category / Owner</label>{{ data.definition.category || 'uncategorized' }} · {{ data.definition.owner }}</div>
              <div class="fp-meta"><label>Unit</label>{{ data.definition.unit || 'unitless' }}</div>
              <div class="fp-meta"><label>Tags</label><div class="fp-chip-list">@for (tag of data.definition.tags; track tag) { <span class="fp-chip">{{ tag }}</span> }</div></div>
              <div class="fp-meta"><label>Updated</label>{{ data.definition.updated_at | date:'medium' }}</div>
            </div>
          </section>

          @if (availability; as state) {
            <section class="fp-panel">
              <div class="fp-panel-title"><div><div class="fp-eyebrow">Source profile · {{ state.source_profile }}</div><h3>Availability</h3></div><app-feature-status-badge [status]="state.execution_readiness"></app-feature-status-badge></div>
              <div class="fp-dimension-grid">
                <div class="fp-dimension"><span>Definition</span><app-feature-status-badge [status]="state.definition_status"></app-feature-status-badge></div>
                <div class="fp-dimension"><span>Version</span><app-feature-status-badge [status]="state.version_status"></app-feature-status-badge></div>
                <div class="fp-dimension"><span>Dependencies</span><app-feature-status-badge [status]="state.dependency_status"></app-feature-status-badge></div>
                <div class="fp-dimension"><span>Data</span><app-feature-status-badge [status]="state.data_status"></app-feature-status-badge></div>
                <div class="fp-dimension"><span>Implementation</span><app-feature-status-badge [status]="state.implementation_status"></app-feature-status-badge></div>
                <div class="fp-dimension"><span>Materialization</span><app-feature-status-badge [status]="state.materialization_status"></app-feature-status-badge></div>
              </div>
              @if (state.reasons.length) { <div class="fp-alert" style="margin-top:12px">{{ state.reasons.join(' · ') }}</div> }
            </section>
          }

          <section class="fp-panel">
            <div class="fp-panel-title"><div><div class="fp-eyebrow">Immutable semantic revisions</div><h3>Versions</h3></div><span class="fp-muted">{{ data.versions.length }} versions</span></div>
            @if (!data.versions.length) { <nz-empty nzNotFoundContent="No versions registered."></nz-empty> }
            <nz-collapse>
              @for (summary of data.versions; track summary.version.id) {
                <nz-collapse-panel [nzHeader]="versionHeader" [nzActive]="summary.version.status === 'published'">
                  <ng-template #versionHeader>
                    <span class="fp-code">v{{ summary.version.version_number }} · ID {{ summary.version.id }}</span>
                    <span style="margin-left:8px"><app-feature-status-badge [status]="summary.version.status"></app-feature-status-badge></span>
                  </ng-template>
                  <div class="fp-meta-grid">
                    <div class="fp-meta"><label>Frequency</label>{{ summary.version.frequency }}</div>
                    <div class="fp-meta"><label>As-of semantics</label>{{ summary.version.as_of_semantics }}</div>
                    <div class="fp-meta"><label>Missing policy</label>{{ summary.version.missing_policy }}</div>
                    <div class="fp-meta"><label>Manifest checksum</label><span class="fp-code">{{ summary.version.manifest_checksum }}</span></div>
                    <div class="fp-meta"><label>Published</label>{{ summary.version.published_at ? (summary.version.published_at | date:'medium') : 'Not published' }}</div>
                    <div class="fp-meta"><label>Quality gate</label><pre class="fp-json">{{ qualityGate(summary.version.manifest_snapshot) | json }}</pre></div>
                  </div>
                  <h4>Implementation</h4>
                  @for (implementation of summary.implementations; track implementation.id) {
                    <div class="fp-meta-grid" style="margin-bottom:8px">
                      <div class="fp-meta"><label>Producer</label>{{ implementation.producer_service }} / {{ implementation.kind }}</div>
                      <div class="fp-meta"><label>Entrypoint</label><span class="fp-code">{{ implementation.entrypoint }}</span></div>
                      <div class="fp-meta"><label>Revision / Status</label>r{{ implementation.implementation_revision }} · <app-feature-status-badge [status]="implementation.status"></app-feature-status-badge></div>
                      <div class="fp-meta"><label>Checksum</label><span class="fp-code">{{ implementation.checksum }}</span></div>
                    </div>
                  } @empty { <div class="fp-alert danger">No implementation is registered for this version.</div> }
                  <h4>Dependencies</h4>
                  <div class="fp-chip-list">
                    @for (dependency of summary.dependencies; track dependency.id) {
                      <span class="fp-chip">{{ dependency.dependency_kind }} · {{ dependencyTarget(dependency.dependency_ref_snapshot) }}</span>
                    } @empty { <span class="fp-muted">No dependencies.</span> }
                  </div>
                </nz-collapse-panel>
              }
            </nz-collapse>
          </section>

          @if (recentRuns.length) {
            <section class="fp-panel">
              <div class="fp-panel-title"><h3>Recent Runs</h3><a class="fp-link" [routerLink]="['../../runs']">View all</a></div>
              <nz-table #runsTable [nzData]="recentRuns" nzSize="small" [nzShowPagination]="false">
                <thead><tr><th>Run ID</th><th>Status</th><th>Source</th><th>As-of</th><th>Revision</th></tr></thead>
                <tbody>@for (run of runsTable.data; track run.run_id) {<tr>
                  <td><a class="fp-link fp-code" [routerLink]="['../../runs', run.run_id]">{{ run.run_id }}</a></td>
                  <td><app-feature-status-badge [status]="run.status"></app-feature-status-badge></td><td>{{ run.source_profile }}</td><td>{{ run.as_of_time | date:'medium' }}</td><td class="fp-code">{{ run.code_revision }}</td>
                </tr>}</tbody>
              </nz-table>
            </section>
          }
        }
      </nz-spin>
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
})
export class DefinitionDetailPageComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(FeaturePlatformApiService);
  private readonly store = inject(FeaturePlatformStore);
  private readonly destroy$ = new Subject<void>();
  detail: FeatureDefinitionDetail | null = null;
  availability: FeatureAvailability | null = null;
  recentRuns: FeatureRun[] = [];
  loading = true;
  error: ReturnType<typeof featurePlatformError> | null = null;

  ngOnInit(): void {
    this.route.paramMap.pipe(
      switchMap((params) => {
        const featureCode = params.get('featureCode') || '';
        this.loading = true;
        this.error = null;
        return this.api.getDefinition(featureCode).pipe(
          switchMap((detail) => {
            const published = detail.versions.map((item) => item.version).filter((item) => item.status === 'published').sort((a, b) => b.version_number - a.version_number)[0];
            return forkJoin({
              detail: of(detail),
              availability: this.api.getAvailability(featureCode, this.store.sourceProfile()).pipe(
                catchError((error) => of(unknownAvailability(featureCode, this.store.sourceProfile(), featurePlatformError(error).message))),
              ),
              runs: published ? this.api.listRuns({ feature_version_id: published.id, limit: 5 }).pipe(catchError(() => of({ items: [], total: 0, limit: 5, offset: 0 }))) : of({ items: [], total: 0, limit: 5, offset: 0 }),
            });
          }),
          takeUntil(this.destroy$),
        );
      }),
      takeUntil(this.destroy$),
    ).subscribe({
      next: ({ detail, availability, runs }) => { this.detail = detail; this.availability = availability; this.recentRuns = runs.items; this.loading = false; },
      error: (error) => { this.error = featurePlatformError(error); this.loading = false; },
    });
  }

  latestPublishedVersion(): number | undefined {
    return this.detail?.versions.map((item) => item.version).filter((item) => item.status === 'published').sort((a, b) => b.version_number - a.version_number)[0]?.version_number;
  }

  qualityGate(snapshot: Record<string, unknown>): unknown { return snapshot['quality'] ?? {}; }
  dependencyTarget(snapshot: Record<string, unknown>): string { return JSON.stringify(snapshot); }
  ngOnDestroy(): void { this.destroy$.next(); this.destroy$.complete(); }
}
