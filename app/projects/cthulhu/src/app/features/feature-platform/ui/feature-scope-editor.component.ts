import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnInit, Output, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NzInputModule } from 'ng-zorro-antd/input';
import { NzRadioModule } from 'ng-zorro-antd/radio';
import { NzSelectModule } from 'ng-zorro-antd/select';
import { SecuritySearchItem } from '../../../core/services/security-lookup.service';
import { SecuritySearchInputComponent } from '../../../shared/ui/security-search-input.component';
import { FeatureRegistryRow, FeatureScopeDraft } from '../models/feature-platform.models';
import { FeaturePlatformStore } from '../state/feature-platform.store';
import { FeatureStatusBadgeComponent } from './feature-status-badge.component';

@Component({
  selector: 'app-feature-scope-editor',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    NzInputModule,
    NzRadioModule,
    NzSelectModule,
    SecuritySearchInputComponent,
    FeatureStatusBadgeComponent,
  ],
  template: `
    <div class="scope-grid">
      <div class="fp-field wide">
        <label>Published Feature</label>
        <nz-select [(ngModel)]="draft.featureCode" (ngModelChange)="selectFeature()" nzShowSearch nzPlaceHolder="Choose a Feature">
          @for (row of publishedRows(); track row.definition.feature_code) {
            <nz-option [nzValue]="row.definition.feature_code" [nzLabel]="row.definition.feature_code + ' · ' + row.definition.display_name"></nz-option>
          }
        </nz-select>
      </div>
      <div class="fp-field">
        <label>Version</label>
        <nz-select [(ngModel)]="draft.version" (ngModelChange)="changed()">
          @for (version of selectedRow()?.published_versions || []; track version.id) {
            <nz-option [nzValue]="version.version_number" [nzLabel]="'v' + version.version_number"></nz-option>
          }
        </nz-select>
      </div>
      <div class="fp-field">
        <label>Readiness</label>
        <app-feature-status-badge [status]="selectedRow()?.availability?.execution_readiness || 'unknown'"></app-feature-status-badge>
      </div>
      <div class="fp-field"><label>Source profile</label><input nz-input [(ngModel)]="draft.sourceProfile" (ngModelChange)="changed()" /></div>
      <div class="fp-field"><label>Market</label><input nz-input [(ngModel)]="draft.market" (ngModelChange)="changed()" /></div>

      <div class="fp-field wide">
        <label>Universe</label>
        <nz-radio-group [(ngModel)]="draft.universeMode" (ngModelChange)="changed()">
          <label nz-radio nzValue="explicit">Explicit securities</label>
          <label nz-radio nzValue="all_active">All active at resolution time</label>
        </nz-radio-group>
      </div>
      @if (draft.universeMode === 'explicit') {
        <div class="fp-field wide">
          <label>Security search</label>
          <app-security-search-input [market]="draft.market" placeholder="Add by company name or symbol" (securitySelected)="addSecurity($event)"></app-security-search-input>
        </div>
        <div class="fp-field wide">
          <label>Security IDs</label>
          <textarea nz-input rows="3" [(ngModel)]="draft.securityIdsText" (ngModelChange)="changed()" placeholder="Positive IDs separated by comma or whitespace"></textarea>
        </div>
      } @else {
        <div class="fp-alert wide">
          All Active must be resolved before execution. The resolved set is current, frozen and not a historical point-in-time universe.
        </div>
      }

      <div class="fp-field wide">
        <label>Evaluation</label>
        <nz-radio-group [(ngModel)]="draft.evaluationMode" (ngModelChange)="changed()">
          <label nz-radio nzValue="point">Point</label>
          <label nz-radio nzValue="range">Bounded range</label>
        </nz-radio-group>
      </div>
      @if (draft.evaluationMode === 'point') {
        <div class="fp-field wide"><label>As-of time</label><input nz-input type="datetime-local" [(ngModel)]="draft.asOf" (ngModelChange)="changed()" /></div>
      } @else {
        <div class="fp-field"><label>Start as-of</label><input nz-input type="datetime-local" [(ngModel)]="draft.startAsOf" (ngModelChange)="changed()" /></div>
        <div class="fp-field"><label>End as-of</label><input nz-input type="datetime-local" [(ngModel)]="draft.endAsOf" (ngModelChange)="changed()" /></div>
        <div class="fp-field wide">
          <label>Step</label>
          <nz-select [(ngModel)]="draft.step" (ngModelChange)="changed()">
            <nz-option nzValue="daily" nzLabel="Daily (calendar days)"></nz-option>
            <nz-option nzValue="weekly" nzLabel="Weekly"></nz-option>
            <nz-option nzValue="monthly" nzLabel="Monthly"></nz-option>
            <nz-option nzValue="quarterly" nzLabel="Quarterly"></nz-option>
          </nz-select>
        </div>
      }

      <div class="fp-field">
        <label>Data cutoff policy</label>
        <nz-select [(ngModel)]="draft.cutoffMode" (ngModelChange)="changed()">
          <nz-option nzValue="same_as_as_of" nzLabel="Same as as-of"></nz-option>
          <nz-option nzValue="lag_seconds" nzLabel="Lag seconds"></nz-option>
        </nz-select>
      </div>
      @if (draft.cutoffMode === 'lag_seconds') {
        <div class="fp-field"><label>Lag seconds</label><input nz-input type="number" min="0" [(ngModel)]="draft.cutoffLagSeconds" (ngModelChange)="changed()" /></div>
      }
    </div>
  `,
  styleUrls: ['../feature-platform-page.scss'],
  styles: [`
    .scope-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
    .wide { grid-column:1/-1; }
    @media(max-width:680px){.scope-grid{grid-template-columns:minmax(0,1fr)}.wide{grid-column:auto}}
  `],
})
export class FeatureScopeEditorComponent implements OnInit {
  readonly store = inject(FeaturePlatformStore);
  @Input({ required: true }) draft!: FeatureScopeDraft;
  @Output() draftChange = new EventEmitter<FeatureScopeDraft>();

  ngOnInit(): void {
    if (!this.store.registryRows().length) this.store.loadRegistry({ status: 'active' });
  }

  publishedRows(): FeatureRegistryRow[] {
    return this.store.registryRows().filter((row) => row.published_versions.length > 0);
  }

  selectedRow(): FeatureRegistryRow | undefined {
    return this.store.registryRows().find((row) => row.definition.feature_code === this.draft.featureCode);
  }

  selectFeature(): void {
    this.draft.version = this.selectedRow()?.latest_published_version?.version_number || null;
    this.changed();
  }

  addSecurity(item: SecuritySearchItem | null): void {
    if (!item) return;
    const ids = this.draft.securityIdsText
      .split(/[\s,]+/)
      .filter(Boolean)
      .map(Number)
      .filter((id) => Number.isInteger(id) && id > 0);
    if (!ids.includes(item.security_id)) ids.push(item.security_id);
    this.draft.securityIdsText = ids.join(', ');
    this.changed();
  }

  changed(): void {
    this.draftChange.emit({ ...this.draft });
  }
}
