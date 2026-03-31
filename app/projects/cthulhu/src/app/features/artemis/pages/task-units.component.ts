import {Component, inject, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormBuilder, FormGroup, FormsModule, ReactiveFormsModule, Validators} from '@angular/forms';
import {ArtemisService} from '../services/artemis.service';
import {NzFormatEmitEvent, NzTreeModule, NzTreeNodeOptions} from 'ng-zorro-antd/tree';
import {NzCardModule} from 'ng-zorro-antd/card';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzInputModule} from 'ng-zorro-antd/input';
import {NzGridModule} from 'ng-zorro-antd/grid';
import {NzMessageService} from 'ng-zorro-antd/message';
import {NzModalModule} from 'ng-zorro-antd/modal';
import {NzFormModule} from 'ng-zorro-antd/form';

@Component({
  selector: 'app-task-units',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    NzTreeModule,
    NzCardModule,
    NzButtonModule,
    NzInputModule,
    NzGridModule,
    NzModalModule,
    NzFormModule
  ],
  template: `
    <div nz-row [nzGutter]="16">
      <div nz-col [nzSpan]="8">
        <nz-card nzTitle="Task Units Explorer" [nzExtra]="explorerExtra">
          <nz-tree
            [nzData]="nodes"
            (nzClick)="onNodeClick($event)">
          </nz-tree>
        </nz-card>
        <ng-template #explorerExtra>
           <button nz-button nzType="primary" nzSize="small" (click)="showCreateModal()">New Task</button>
        </ng-template>
        <!-- Actions for selected file -->
        <div *ngIf="currentFile" style="margin-top: 8px; display: flex; gap: 8px;">
            <button nz-button nzSize="small" (click)="showRenameModal()">Rename</button>
            <button nz-button nzSize="small" nzDanger (click)="deleteFile()">Delete</button>
        </div>
      </div>
      <div nz-col [nzSpan]="16">
        <nz-card [nzTitle]="currentFile ? 'Editing: ' + currentFile : 'Select a file'" [nzExtra]="extraTemplate">
          <textarea
            *ngIf="currentFile"
            nz-input
            [(ngModel)]="fileContent"
            [nzAutosize]="{ minRows: 20, maxRows: 30 }"
            style="font-family: 'Consolas', 'Monaco', 'Courier New', monospace; line-height: 1.5; font-size: 14px;">
          </textarea>
          <div *ngIf="!currentFile" style="text-align: center; color: #ccc; padding: 50px;">
            Select a file from the tree to edit
          </div>
        </nz-card>
      </div>
    </div>
    <ng-template #extraTemplate>
      <button *ngIf="currentFile" nz-button nzType="primary" (click)="save()">Save File</button>
    </ng-template>

    <nz-modal
      [(nzVisible)]="isVisible"
      nzTitle="Create New Task Unit"
      (nzOnCancel)="handleCancel()"
      (nzOnOk)="handleCreate()"
      [nzOkLoading]="isConfirmLoading"
    >
      <ng-container *nzModalContent>
        <form nz-form [formGroup]="validateForm">
          <nz-form-item>
            <nz-form-label [nzSm]="6" [nzXs]="24" nzRequired nzFor="directory">Directory</nz-form-label>
            <nz-form-control [nzSm]="14" [nzXs]="24" nzErrorTip="Please input directory!">
              <input nz-input formControlName="directory" id="directory" placeholder="Relative path, e.g. zh/" />
            </nz-form-control>
          </nz-form-item>
          <nz-form-item>
            <nz-form-label [nzSm]="6" [nzXs]="24" nzRequired nzFor="filename">Filename</nz-form-label>
            <nz-form-control [nzSm]="14" [nzXs]="24" nzErrorTip="Please input filename (.py)!">
              <input nz-input formControlName="filename" id="filename" placeholder="e.g. my_task.py" />
            </nz-form-control>
          </nz-form-item>
        </form>
      </ng-container>
    </nz-modal>

    <nz-modal
      [(nzVisible)]="isRenameVisible"
      nzTitle="Rename File"
      (nzOnCancel)="isRenameVisible = false"
      (nzOnOk)="handleRename()"
      [nzOkLoading]="isConfirmLoading"
    >
      <ng-container *nzModalContent>
        <input nz-input [(ngModel)]="newFilename" placeholder="New filename or path" />
      </ng-container>
    </nz-modal>
  `
})
export class TaskUnitsComponent implements OnInit {
  private service = inject(ArtemisService);
  private message = inject(NzMessageService);
  private fb = inject(FormBuilder);

  nodes: NzTreeNodeOptions[] = [];
  currentFile = '';
  fileContent = '';

  // Create Modal
  isVisible = false;
  isConfirmLoading = false;
  validateForm!: FormGroup;

  // Rename
  isRenameVisible = false;
  newFilename = '';

  ngOnInit() {
    this.loadTree();
    this.validateForm = this.fb.group({
      directory: ['', [Validators.required]],
      filename: ['', [Validators.required, Validators.pattern(/.*\.py$/)]]
    });
  }

  loadTree() {
    this.service.getTaskUnitsTree().subscribe(res => {
      this.nodes = res.items.map(item => this.mapNode(item));
    });
  }

  mapNode(item: any): NzTreeNodeOptions {
    return {
      title: item.name,
      key: item.path,
      isLeaf: item.type === 'file',
      children: item.children ? item.children.map((c: any) => this.mapNode(c)) : [],
      expanded: true,
      selectable: item.type === 'file'
    };
  }

  onNodeClick(event: NzFormatEmitEvent) {
    const node = event.node!;
    if (node.isLeaf) {
      this.currentFile = node.key;
      this.service.getTaskUnitFile(this.currentFile).subscribe(res => {
        this.fileContent = res.content;
      });
    } else {
        // If folder selected, maybe update directory input for create
        this.validateForm.patchValue({ directory: node.key + '/' });
    }
  }

  save() {
    if (!this.currentFile) return;
    this.service.updateTaskUnitFile(this.currentFile, this.fileContent).subscribe({
      next: () => this.message.success('File saved successfully'),
      error: (err) => this.message.error('Failed to save file: ' + err.message)
    });
  }

  showCreateModal() {
      this.isVisible = true;
      // Default directory if not set?
      if (!this.validateForm.value.directory) {
          this.validateForm.patchValue({ directory: '' });
      }
  }

  handleCancel() {
      this.isVisible = false;
  }

  handleCreate() {
      if (this.validateForm.valid) {
          this.isConfirmLoading = true;
          const dir = this.validateForm.value.directory.endsWith('/') ? this.validateForm.value.directory : this.validateForm.value.directory + '/';
          const fullPath = (dir + this.validateForm.value.filename).replace(/^\/+/, ''); // remove leading slashes

          const template = `from artemis.task_units.base import BaseTaskUnit
from artemis.core.context import TaskContext

class MyTask(BaseTaskUnit):
    def execute(self, ctx: TaskContext):
        ctx.logger.info("Hello from MyTask")
        return "success"
`;
          this.service.createTaskUnitFile(fullPath, template).subscribe({
              next: () => {
                  this.message.success('Task unit created successfully');
                  this.isVisible = false;
                  this.isConfirmLoading = false;
                  this.loadTree(); // Refresh tree

                  // Optionally open the new file
                  this.currentFile = fullPath;
                  this.fileContent = template;
              },
              error: (err) => {
                  this.message.error('Failed to create task unit: ' + err.error?.detail || err.message);
                  this.isConfirmLoading = false;
              }
          });
      } else {
          Object.values(this.validateForm.controls).forEach(control => {
            if (control.invalid) {
              control.markAsDirty();
              control.updateValueAndValidity({ onlySelf: true });
            }
          });
      }
  }

  showRenameModal() {
      if (!this.currentFile) return;
      this.newFilename = this.currentFile;
      this.isRenameVisible = true;
  }

  handleRename() {
      if (!this.newFilename) return;
      this.isConfirmLoading = true;
      this.service.renameTaskUnit(this.currentFile, this.newFilename).subscribe({
          next: () => {
              this.message.success('File renamed successfully');
              this.isRenameVisible = false;
              this.isConfirmLoading = false;
              this.currentFile = ''; // Deselect
              this.fileContent = '';
              this.loadTree();
          },
          error: (err) => {
              this.message.error('Failed to rename: ' + err.message);
              this.isConfirmLoading = false;
          }
      });
  }

  deleteFile() {
      if (!this.currentFile) return;
      if (!confirm(`Are you sure you want to delete ${this.currentFile}? This will unregister any associated dynamic tasks.`)) return;

      this.service.deleteTaskUnit(this.currentFile).subscribe({
          next: () => {
              this.message.success('File deleted successfully');
              this.currentFile = '';
              this.fileContent = '';
              this.loadTree();
          },
          error: (err) => {
              this.message.error('Failed to delete: ' + (err.error?.detail || err.message));
          }
      });
  }
}
