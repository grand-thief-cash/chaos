import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, combineLatest, switchMap, takeUntil } from 'rxjs';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { NzEmptyModule } from 'ng-zorro-antd/empty';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { NzSpinModule } from 'ng-zorro-antd/spin';
import { FeatureLineage, FeatureLineageVersion } from '../models/feature-platform.models';
import { featurePlatformError } from '../models/feature-platform.utils';
import { FeaturePlatformApiService } from '../services/feature-platform-api.service';
import { FeatureStatusBadgeComponent } from '../ui/feature-status-badge.component';

@Component({
  selector: 'app-feature-lineage-page',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NzButtonModule, NzEmptyModule, NzSelectModule, NzSpinModule, FeatureStatusBadgeComponent],
  template: `
    <div class="fp-page">
      <section class="fp-toolbar">
        <div><div class="fp-eyebrow">Recursive dependency graph</div><h2 style="margin:3px 0 0">Lineage · <span class="fp-code">{{ lineage?.feature_code }}</span></h2></div>
        <div class="fp-toolbar-fields">
          <div class="fp-field"><label>Version</label><nz-select [(ngModel)]="selectedVersionId" (ngModelChange)="selectVersion($event)" style="width:150px">
            @for (version of lineage?.versions || []; track version.feature_version_id) { <nz-option [nzValue]="version.feature_version_id" [nzLabel]="'v' + version.version_number + ' · ID ' + version.feature_version_id"></nz-option> }
          </nz-select></div>
          <a nz-button [routerLink]="['../../definitions', lineage?.feature_code]">Definition</a>
        </div>
      </section>
      @if (error) { <div class="fp-alert danger"><strong>{{ error.code }}</strong> {{ error.message }}</div> }
      <nz-spin [nzSpinning]="loading">
        @if (selected(); as version) {
          <section class="lineage-board">
            <div class="lineage-column">
              <div class="column-label">UPSTREAM DATA + FEATURES</div>
              @for (field of version.upstream_data_fields; track field.data_field_dictionary_id) {
                <a class="lineage-node field" [routerLink]="['/phoenixa/catalog/govern/data_field_dictionary']">
                  <span class="node-kind">DATA FIELD · {{ field.source }}</span>
                  <strong>{{ field.dataset }}.{{ field.raw_field }}</strong>
                  <small>{{ field.data_type }} · contract {{ field.contract_version }}</small>
                  @if (field.deprecated) { <app-feature-status-badge status="deprecated"></app-feature-status-badge> }
                </a>
              }
              @for (upstream of version.upstream_features; track upstream.feature_version_id) {
                <a class="lineage-node" [routerLink]="['../../definitions', upstream.feature_code]">
                  <span class="node-kind">FEATURE VERSION</span><strong>{{ upstream.feature_code }}</strong><small>v{{ upstream.version_number }} · ID {{ upstream.feature_version_id }}</small><app-feature-status-badge [status]="upstream.status"></app-feature-status-badge>
                </a>
              }
              @if (!version.upstream_data_fields.length && !version.upstream_features.length) { <div class="lineage-empty">No upstream dependencies.</div> }
            </div>
            <div class="lineage-column current">
              <div class="column-label">SELECTED VERSION</div>
              <div class="lineage-node root"><span class="node-kind">ROOT</span><strong>{{ lineage?.feature_code }}</strong><small>v{{ version.version_number }} · ID {{ version.feature_version_id }}</small></div>
              <div class="graph-note">{{ version.upstream.length }} direct upstream · {{ version.downstream.length }} direct downstream</div>
            </div>
            <div class="lineage-column">
              <div class="column-label">DOWNSTREAM FEATURES</div>
              @for (downstream of version.downstream_features; track downstream.feature_version_id) {
                <a class="lineage-node downstream" [routerLink]="['../../definitions', downstream.feature_code]">
                  <span class="node-kind">FEATURE VERSION</span><strong>{{ downstream.feature_code }}</strong><small>v{{ downstream.version_number }} · ID {{ downstream.feature_version_id }}</small><app-feature-status-badge [status]="downstream.status"></app-feature-status-badge>
                </a>
              }
              @if (!version.downstream_features.length) { <div class="lineage-empty">No downstream consumers.</div> }
            </div>
          </section>
        } @else if (!loading) { <nz-empty nzNotFoundContent="No lineage versions are available."></nz-empty> }
      </nz-spin>
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
  styles: [`
    .lineage-board { display: grid; grid-template-columns: minmax(220px,1fr) minmax(210px,.72fr) minmax(220px,1fr); gap: 32px; padding: 20px; border: 1px solid #d8d3c9; background: rgba(255,255,255,.92); overflow-x: auto; }
    .lineage-column { position: relative; display: flex; flex-direction: column; gap: 9px; min-width: 210px; }
    .lineage-column:not(:last-child)::after { content: ''; position: absolute; top: 50%; right: -24px; width: 17px; border-top: 2px solid #c46b32; }
    .lineage-column:not(:last-child)::before { content: ''; position: absolute; z-index: 1; top: calc(50% - 4px); right: -25px; border-left: 7px solid #c46b32; border-top: 4px solid transparent; border-bottom: 4px solid transparent; }
    .column-label { margin-bottom: 4px; color: #7b746b; font: 700 10px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .12em; }
    .lineage-node { display: grid; gap: 4px; padding: 12px; color: #25313b; border: 1px solid #cdc8bd; border-left: 4px solid #517b8e; background: #fff; box-shadow: 0 5px 12px rgba(38,43,48,.06); }
    .lineage-node:hover { border-color: #d96c24; transform: translateY(-1px); }
    .lineage-node.field { border-left-color: #a99043; background: #fffdf4; }
    .lineage-node.downstream { border-left-color: #758c65; }
    .lineage-node.root { justify-content: center; min-height: 124px; border: 2px solid #c65f22; background: linear-gradient(145deg,#fffaf1,#f4e8d7); }
    .node-kind { color: #7b7369; font: 700 9px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .09em; }
    .lineage-node strong { font-size: 13px; overflow-wrap: anywhere; }
    .lineage-node small { color: #727b83; }
    .graph-note, .lineage-empty { padding: 10px; color: #7b8188; border: 1px dashed #cbc6bc; text-align: center; font-size: 12px; }
    @media (max-width: 900px) { .lineage-board { grid-template-columns: 1fr; } .lineage-column::after, .lineage-column::before { display:none; } }
  `],
})
export class LineagePageComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(FeaturePlatformApiService);
  private readonly destroy$ = new Subject<void>();
  lineage: FeatureLineage | null = null;
  selectedVersionId: number | null = null;
  loading = true;
  error: ReturnType<typeof featurePlatformError> | null = null;

  ngOnInit(): void {
    combineLatest([this.route.paramMap, this.route.queryParamMap]).pipe(
      switchMap(([params, query]) => {
        this.loading = true;
        const requested = Number(query.get('version_id')) || null;
        return this.api.getLineage(params.get('featureCode') || '').pipe(takeUntil(this.destroy$), switchMap((lineage) => {
          this.lineage = lineage;
          this.selectedVersionId = lineage.versions.some((item) => item.feature_version_id === requested) ? requested : lineage.versions[0]?.feature_version_id ?? null;
          return [lineage];
        }));
      }),
      takeUntil(this.destroy$),
    ).subscribe({ next: () => { this.loading = false; }, error: (error) => { this.error = featurePlatformError(error); this.loading = false; } });
  }

  selected(): FeatureLineageVersion | undefined { return this.lineage?.versions.find((item) => item.feature_version_id === this.selectedVersionId); }
  selectVersion(versionId: number): void { this.router.navigate([], { relativeTo: this.route, queryParams: { version_id: versionId }, replaceUrl: true }); }
  ngOnDestroy(): void { this.destroy$.next(); this.destroy$.complete(); }
}
