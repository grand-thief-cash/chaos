import {CommonModule} from '@angular/common';
import {Component, inject} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {KnowledgeEntity} from '../models/atlas.models';
import {AtlasApiService} from '../services/atlas-api.service';

@Component({
  selector: 'app-atlas-entity-review',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <h1>Entity review</h1>
      <p>
        Review provisional or ambiguous entities before treating them as governed
        knowledge entities. Security registry links remain controlled by Atlas resolution.
      </p>
      <div>
        <input [(ngModel)]="query" placeholder="Canonical name or alias">
        <button (click)="load()">Search</button>
      </div>
      <table *ngIf="entities.length">
        <thead>
          <tr><th>Name</th><th>Type</th><th>Country</th><th>Resolution</th><th></th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let entity of entities">
            <td><input [(ngModel)]="entity.canonical_name"></td>
            <td>{{entity.entity_type}}</td>
            <td><input class="short" [(ngModel)]="entity.country_code"></td>
            <td>
              <select [(ngModel)]="entity.resolution_state">
                <option value="PROVISIONAL">PROVISIONAL</option>
                <option value="AMBIGUOUS">AMBIGUOUS</option>
                <option value="RESOLVED_KNOWLEDGE_ENTITY">RESOLVED_KNOWLEDGE_ENTITY</option>
                <option value="RESOLVED_SECURITY">RESOLVED_SECURITY</option>
              </select>
            </td>
            <td><button (click)="save(entity)">Save</button></td>
          </tr>
        </tbody>
      </table>
      <p>{{message}}</p>
    </section>
  `,
  styles: [`
    .page{padding:24px}input,select{padding:7px}.short{width:72px}
    button{margin-left:8px;padding:7px 12px}table{width:100%;border-collapse:collapse;margin-top:16px}
    th,td{text-align:left;padding:8px;border-bottom:1px solid #eee}
  `],
})
export class EntityReviewComponent {
  private api = inject(AtlasApiService);
  query = '';
  entities: KnowledgeEntity[] = [];
  message = '';

  load(): void {
    this.api.entities(this.query).subscribe({
      next: result => this.entities = result.data,
      error: error => this.message = error.message,
    });
  }

  save(entity: KnowledgeEntity): void {
    this.api.saveEntities([entity]).subscribe({
      next: () => this.message = `Saved ${entity.canonical_name}.`,
      error: error => this.message = error.message,
    });
  }
}
