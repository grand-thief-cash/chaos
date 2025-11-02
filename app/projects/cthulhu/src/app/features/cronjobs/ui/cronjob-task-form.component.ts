import {Component, EventEmitter, Input, OnChanges, Output, SimpleChanges} from '@angular/core';
import {CommonModule} from '@angular/common';
import {FormBuilder, ReactiveFormsModule, Validators} from '@angular/forms';
import {Task} from '../models/cronjob.model';
import {NzFormModule} from 'ng-zorro-antd/form';
import {NzInputModule} from 'ng-zorro-antd/input';
import {NzSelectModule} from 'ng-zorro-antd/select';
import {NzInputNumberModule} from 'ng-zorro-antd/input-number';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzMessageModule, NzMessageService} from 'ng-zorro-antd/message';

@Component({
  selector: 'cronjob-task-form',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, NzFormModule, NzInputModule, NzSelectModule, NzInputNumberModule, NzButtonModule, NzMessageModule],
  template: `
  <form nz-form [formGroup]="form" nzLayout="horizontal" (ngSubmit)="submit()" class="task-form">
      <nz-form-item>
        <nz-form-label>名称</nz-form-label>
        <nz-form-control nzHasFeedback [nzErrorTip]="'必填，最长128字符'">
          <input nz-input formControlName="name" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>描述</nz-form-label>
        <nz-form-control>
          <textarea nz-input formControlName="description" rows="2"></textarea>
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>Cron表达式</nz-form-label>
        <nz-form-control nzHasFeedback [nzErrorTip]="'必填'">
          <input nz-input formControlName="cron_expr" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>Timezone</nz-form-label>
        <nz-form-control>
          <input nz-input formControlName="timezone" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>执行类型</nz-form-label>
        <nz-form-control>
          <nz-select formControlName="exec_type">
            <nz-option nzValue="SYNC" nzLabel="SYNC"></nz-option>
            <nz-option nzValue="ASYNC" nzLabel="ASYNC"></nz-option>
          </nz-select>
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>HTTP Method</nz-form-label>
        <nz-form-control>
          <input nz-input formControlName="http_method" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>Target URL</nz-form-label>
        <nz-form-control nzHasFeedback [nzErrorTip]="'必填'">
          <input nz-input formControlName="target_url" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>Headers(JSON)</nz-form-label>
        <nz-form-control>
          <textarea nz-input formControlName="headers_json" rows="2"></textarea>
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>Body模板</nz-form-label>
        <nz-form-control>
          <textarea nz-input formControlName="body_template" rows="2"></textarea>
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>超时(秒)</nz-form-label>
        <nz-form-control>
          <nz-input-number formControlName="timeout_seconds" [nzMin]="1" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>重试策略(JSON)</nz-form-label>
        <nz-form-control>
          <textarea nz-input formControlName="retry_policy_json" rows="2"></textarea>
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>最大并发</nz-form-label>
        <nz-form-control>
          <nz-input-number formControlName="max_concurrency" [nzMin]="1" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>并发策略</nz-form-label>
        <nz-form-control>
          <input nz-input formControlName="concurrency_policy" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>回调Method</nz-form-label>
        <nz-form-control>
          <input nz-input formControlName="callback_method" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>回调超时(秒)</nz-form-label>
        <nz-form-control>
          <nz-input-number formControlName="callback_timeout_sec" [nzMin]="1" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>Overlap Action</nz-form-label>
        <nz-form-control>
          <input nz-input formControlName="overlap_action" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>Failure Action</nz-form-label>
        <nz-form-control>
          <input nz-input formControlName="failure_action" />
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>状态</nz-form-label>
        <nz-form-control>
          <nz-select formControlName="status">
            <nz-option nzValue="ENABLED" nzLabel="ENABLED"></nz-option>
            <nz-option nzValue="DISABLED" nzLabel="DISABLED"></nz-option>
          </nz-select>
        </nz-form-control>
      </nz-form-item>
    <div class="actions">
      <button nz-button nzType="primary" type="submit" [disabled]="form.invalid">保存</button>
      <button nz-button nzType="default" type="button" (click)="cancel.emit()">取消</button>
    </div>
  </form>
  `,
  styles: [`
    .task-form { max-width: 1000px; }
    .task-form .ant-form-item { margin-bottom: 12px; }
    .task-form .ant-form-item-label { flex: 0 0 170px; } /* 标签列宽度 */
    .task-form .ant-form-item-label > label { width: 170px; }
    @media (max-width: 768px) {
      .task-form [nz-form] { width: 100%; }
      .task-form .ant-form-item-label { flex: 0 0 100%; text-align:left; }
      .task-form .ant-form-item-label > label { width: auto; }
    }
    .actions { margin-top: 16px; display:flex; gap:12px; }
  `]
})
export class CronjobTaskFormComponent implements OnChanges { // 实现 OnChanges
  @Input() value: Partial<Task> | null = null;
  @Output() save = new EventEmitter<Partial<Task>>();
  @Output() cancel = new EventEmitter<void>();

  form = this.fb.nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(128)]],
    description: [''],
    cron_expr: ['', Validators.required],
    timezone: ['UTC'],
    exec_type: ['SYNC'],
    http_method: ['GET'],
    target_url: ['', Validators.required],
    headers_json: ['{}'],
    body_template: [''],
    timeout_seconds: [30],
    retry_policy_json: ['{}'],
    max_concurrency: [1],
    concurrency_policy: ['PARALLEL'],
    callback_method: ['POST'],
    callback_timeout_sec: [10],
    overlap_action: ['SKIP'],
    failure_action: ['ALERT'],
    status: ['ENABLED']
  });

  constructor(private fb: FormBuilder, private msg: NzMessageService) {}
  ngOnChanges(changes: SimpleChanges){
    if(this.value){
      this.form.patchValue(this.value);
    }
  }
  submit(){
    if(this.form.valid){
      const raw = this.form.getRawValue();
      const payload: Partial<Task> = {
        ...this.value,
        ...raw,
        exec_type: raw.exec_type === 'ASYNC' ? 'ASYNC' : 'SYNC',
        status: raw.status === 'DISABLED' ? 'DISABLED' : 'ENABLED'
      };
      this.save.emit(payload);
      this.msg.success('表单已提交');
    }
  }
}
