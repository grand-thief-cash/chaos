import {Component, inject, OnInit} from '@angular/core';
import {CommonModule} from '@angular/common';
import {ArtemisService} from '../services/artemis.service';
import {ArtemisTask, TaskUnitRegisterReq, UnregisteredTask} from '../models/artemis.models';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzCardModule} from 'ng-zorro-antd/card';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzModalModule} from 'ng-zorro-antd/modal';
import {NzFormModule} from 'ng-zorro-antd/form';
import {NzInputModule} from 'ng-zorro-antd/input';
import {NzTabsModule} from 'ng-zorro-antd/tabs';
import {FormBuilder, FormGroup, ReactiveFormsModule, Validators} from '@angular/forms';
import {NzMessageService} from 'ng-zorro-antd/message';

@Component({
  selector: 'app-task-list',
  standalone: true,
  imports: [
    CommonModule,
    NzTableModule,
    NzCardModule,
    NzButtonModule,
    NzModalModule,
    NzFormModule,
    NzInputModule,
    NzTabsModule,
    ReactiveFormsModule
  ],
  template: `
    <nz-card>
      <nz-tabset>
        <nz-tab nzTitle="Registered Tasks">
            <nz-table #basicTable [nzData]="tasks" [nzLoading]="loading">
                <thead>
                <tr>
                    <th>Task Code</th>
                    <th>Implementation Class</th>
                    <th>Module</th>
                    <th>Action</th>
                </tr>
                </thead>
                <tbody>
                <tr *ngFor="let data of basicTable.data">
                    <td>{{ data.task_code }}</td>
                    <td>{{ data.impl }}</td>
                    <td>{{ data.module }}</td>
                    <td>
                        <button *ngIf="data.is_dynamic" nz-button nzType="link" nzDanger (click)="unregister(data)">Unregister</button>
                    </td>
                </tr>
                </tbody>
            </nz-table>
        </nz-tab>
        <nz-tab nzTitle="Unregistered Tasks" (nzClick)="loadUnregistered()">
             <nz-table #unregTable [nzData]="unregisteredTasks" [nzLoading]="loadingUnreg">
                <thead>
                <tr>
                    <th>Task Code</th>
                    <th>Implementation Class</th>
                    <th>Module</th>
                    <th>Action</th>
                </tr>
                </thead>
                <tbody>
                <tr *ngFor="let data of unregTable.data">
                    <td>{{ data.task_code }}</td>
                    <td>{{ data.class_name }}</td>
                    <td>{{ data.module }}</td>
                    <td>
                        <button nz-button nzType="link" (click)="quickRegister(data)">Register</button>
                    </td>
                </tr>
                </tbody>
            </nz-table>
        </nz-tab>
      </nz-tabset>
    </nz-card>


    <nz-modal
      [(nzVisible)]="isVisible"
      nzTitle="Register Task"
      (nzOnCancel)="handleCancel()"
      (nzOnOk)="handleOk()"
      [nzOkLoading]="isConfirmLoading"
    >
      <ng-container *nzModalContent>
        <form nz-form [formGroup]="validateForm">
          <nz-form-item>
            <nz-form-label [nzSm]="6" [nzXs]="24" nzRequired nzFor="task_code">Task Code</nz-form-label>
            <nz-form-control [nzSm]="14" [nzXs]="24" nzErrorTip="Please input task code!">
              <input nz-input formControlName="task_code" id="task_code" />
            </nz-form-control>
          </nz-form-item>
          <nz-form-item>
            <nz-form-label [nzSm]="6" [nzXs]="24" nzRequired nzFor="module">Module</nz-form-label>
            <nz-form-control [nzSm]="14" [nzXs]="24" nzErrorTip="Please input module!">
              <input nz-input formControlName="module" id="module" [readonly]="true" />
            </nz-form-control>
          </nz-form-item>
          <nz-form-item>
            <nz-form-label [nzSm]="6" [nzXs]="24" nzRequired nzFor="class_name">Class Name</nz-form-label>
            <nz-form-control [nzSm]="14" [nzXs]="24" nzErrorTip="Please input class name!">
              <input nz-input formControlName="class_name" id="class_name" [readonly]="true" />
            </nz-form-control>
          </nz-form-item>
        </form>
      </ng-container>
    </nz-modal>
  `
})
export class TaskListComponent implements OnInit {
  private service = inject(ArtemisService);
  private fb = inject(FormBuilder);
  private message = inject(NzMessageService);

  tasks: ArtemisTask[] = [];
  unregisteredTasks: UnregisteredTask[] = [];
  loading = true;
  loadingUnreg = false;
  isVisible = false;
  isConfirmLoading = false;
  validateForm!: FormGroup;

  ngOnInit() {
    this.refreshTasks();
    this.validateForm = this.fb.group({
      task_code: [null, [Validators.required]],
      module: [null, [Validators.required]],
      class_name: [null, [Validators.required]]
    });
  }

  refreshTasks() {
    this.loading = true;
    this.service.getTasks().subscribe({
        next: (res) => {
            this.tasks = res.tasks;
            this.loading = false;
        },
        error: (err) => {
           console.error(err);
           this.loading = false;
        }
    });
  }

  loadUnregistered() {
      this.loadingUnreg = true;
      this.service.getUnregisteredTasks().subscribe({
          next: (res) => {
              this.unregisteredTasks = res.tasks;
              this.loadingUnreg = false;
          },
          error: (err) => {
              this.message.error('Failed to load unregistered tasks');
              this.loadingUnreg = false;
          }
      });
  }

  quickRegister(data: UnregisteredTask) {
      this.isVisible = true;
      this.validateForm.patchValue({
          task_code: data.task_code, // Default to suggested task_code
          module: data.module,
          class_name: data.class_name
      });
  }

  showRegisterModal(): void {
    this.isVisible = true;
    this.validateForm.reset();
  }

  handleOk(): void {
    if (this.validateForm.valid) {
      this.isConfirmLoading = true;
      const req: TaskUnitRegisterReq = this.validateForm.value;
      this.service.registerTaskUnit(req).subscribe({
        next: () => {
          this.message.success('Task registered successfully');
          this.isVisible = false;
          this.isConfirmLoading = false;
          this.refreshTasks();
          this.loadUnregistered(); // Refresh unregistered list
        },
        error: (err) => {
          this.message.error('Failed to register task: ' + err.error?.detail || err.message);
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

  handleCancel(): void {
    this.isVisible = false;
  }

  unregister(task: ArtemisTask) {
      if (!confirm(`Are you sure you want to unregister ${task.task_code}?`)) return;

      this.service.unregisterTask(task.task_code).subscribe({
          next: () => {
              this.message.success('Task unregistered');
              this.refreshTasks();
          },
          error: (err) => this.message.error('Failed to unregister: ' + err.message)
      });
  }
}
