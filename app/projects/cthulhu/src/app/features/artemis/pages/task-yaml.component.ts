import {Component, inject, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {ArtemisService} from '../services/artemis.service';
import {NzCardModule} from 'ng-zorro-antd/card';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzMessageService} from 'ng-zorro-antd/message';
import * as yaml from 'js-yaml';
import {YamlEditorComponent} from '../../../shared/ui/yaml-editor/yaml-editor.component';

@Component({
  selector: 'app-task-yaml',
  standalone: true,
  imports: [CommonModule, NzCardModule, NzButtonModule, YamlEditorComponent],
  template: `
    <nz-card [nzTitle]="'Edit task.yaml'" [nzExtra]="extraTemplate">
      <app-yaml-editor
        [value]="content"
        (valueChange)="onContentChange($event)"
        [minHeightPx]="600">
      </app-yaml-editor>
    </nz-card>

    <ng-template #extraTemplate>
      <button nz-button nzType="primary" (click)="save()">Save Configuration</button>
    </ng-template>
  `
})
export class TaskYamlComponent implements OnInit {
  private service = inject(ArtemisService);
  private message = inject(NzMessageService);

  content = '';

  ngOnInit() {
    this.service.getTaskYaml().subscribe(res => {
      this.content = res.content;
    });
  }

  onContentChange(value: string) {
    this.content = value;
  }

  save() {
    try {
      yaml.load(this.content);
    } catch (e: any) {
      this.message.error('Invalid YAML: ' + e.message);
      return;
    }

    this.service.updateTaskYaml(this.content).subscribe({
      next: () => this.message.success('Configuration saved successfully'),
      error: (err) => this.message.error('Failed to save configuration: ' + err.message)
    });
  }
}
