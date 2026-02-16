import {Component, inject, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormsModule} from '@angular/forms';
import {ArtemisService} from '../services/artemis.service';
import {NzCardModule} from 'ng-zorro-antd/card';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzInputModule} from 'ng-zorro-antd/input';
import {NzMessageService} from 'ng-zorro-antd/message';
import {NzGridModule} from 'ng-zorro-antd/grid';
import {NzTreeModule, NzTreeNodeOptions} from 'ng-zorro-antd/tree';
import * as yaml from 'js-yaml';

@Component({
  selector: 'app-task-yaml',
  standalone: true,
  imports: [CommonModule, FormsModule, NzCardModule, NzButtonModule, NzInputModule, NzGridModule, NzTreeModule],
  template: `
    <div nz-row [nzGutter]="16">
      <div nz-col [nzSpan]="10">
        <nz-card nzTitle="Configuration Structure" [nzBodyStyle]="{ 'max-height': '600px', 'overflow': 'auto' }">
          <nz-tree
            [nzData]="nodes"
            [nzExpandAll]="true">
          </nz-tree>
        </nz-card>
      </div>
      <div nz-col [nzSpan]="14">
        <nz-card [nzTitle]="'Edit task.yaml'" [nzExtra]="extraTemplate">
          <textarea
            nz-input
            [(ngModel)]="content"
            (ngModelChange)="onContentChange($event)"
            [nzAutosize]="{ minRows: 25, maxRows: 30 }"
            style="font-family: 'Consolas', 'Monaco', monospace; font-size: 14px; line-height: 1.5;"></textarea>
        </nz-card>
      </div>
    </div>
    <ng-template #extraTemplate>
      <button nz-button nzType="primary" (click)="save()">Save Configuration</button>
    </ng-template>
  `
})
export class TaskYamlComponent implements OnInit {
  private service = inject(ArtemisService);
  private message = inject(NzMessageService);
  content = '';
  nodes: NzTreeNodeOptions[] = [];

  ngOnInit() {
    this.service.getTaskYaml().subscribe(res => {
      this.content = res.content;
      this.updateTree(this.content);
    });
  }

  onContentChange(value: string) {
    this.updateTree(value);
  }

  updateTree(yamlContent: string) {
    try {
      const obj = yaml.load(yamlContent);
      if (typeof obj === 'object' && obj !== null) {
        this.nodes = this.buildTree(obj);
      } else {
        this.nodes = [];
      }
    } catch (e) {
      // invalid yaml, don't update tree or maybe clear
      // simplistic approach: just ignore updates until valid
    }
  }

  buildTree(obj: any, key: string = 'root'): NzTreeNodeOptions[] {
      if (typeof obj !== 'object' || obj === null) {
          return [{ title: `${key}: ${String(obj)}`, key: key, isLeaf: true }];
      }

      if (Array.isArray(obj)) {
          return obj.map((item, index) => ({
              title: `[${index}]`,
              key: `${key}-${index}`,
              children: this.buildTree(item, `${key}-${index}`),
              isLeaf: typeof item !== 'object'
          }));
      }

      return Object.keys(obj).map(k => {
          const value = obj[k];
          const isLeaf = typeof value !== 'object' || value === null;
          return {
              title: k,
              key: `${key}-${k}`,
              children: isLeaf ? [{ title: String(value), key: `${key}-${k}-val`, isLeaf: true }] : this.buildTree(value, `${key}-${k}`),
              isLeaf: false // parent node with children
          };
      });
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
