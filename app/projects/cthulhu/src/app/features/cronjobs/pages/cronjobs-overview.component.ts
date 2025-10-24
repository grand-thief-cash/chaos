import {Component, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {CronjobsStore} from '../state/cronjobs.store';

@Component({
  selector: 'app-cronjobs-overview',
  standalone: true,
  imports: [CommonModule],
  template: `<div class="feature-page">
  <h2>Cron Jobs Overview</h2>
  <div style="margin-bottom:8px; display:flex; gap:8px;">
    <button (click)="reload()">Reload</button>
    <span *ngIf="store.loading()">Loading...</span>
    <span *ngIf="store.error()" style="color:red">{{store.error()}}</span>
  </div>
  <table border="1" cellpadding="6" *ngIf="store.items().length; else emptyTpl">
    <thead>
      <tr><th>Name</th><th>Schedule</th><th>Status</th></tr>
    </thead>
    <tbody>
      <tr *ngFor="let cj of store.items()">
        <td>{{cj.name}}</td>
        <td>{{cj.schedule}}</td>
        <td>{{cj.status}}</td>
      </tr>
    </tbody>
  </table>
  <ng-template #emptyTpl>
    <div *ngIf="!store.loading() && !store.error()">No cronjobs loaded.</div>
  </ng-template>
</div>`
})
export class CronjobsOverviewComponent implements OnInit {
  constructor(public store: CronjobsStore) {}
  ngOnInit(){ this.store.loadAll(); }
  reload(){ this.store.loadAll(true); }
}
