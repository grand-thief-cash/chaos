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
import {NzCollapseModule} from 'ng-zorro-antd/collapse';
import {FormsModule} from '@angular/forms';

@Component({
  selector: 'cronjob-task-form',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, NzFormModule, NzInputModule, NzSelectModule, NzInputNumberModule, NzButtonModule, NzMessageModule, NzCollapseModule],
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
        <nz-form-label>Method</nz-form-label>
        <nz-form-control>
          <nz-select formControlName="method">
            <nz-option *ngFor="let m of httpMethods" [nzValue]="m" [nzLabel]="m"></nz-option>
          </nz-select>
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>Target Service</nz-form-label>
        <nz-form-control nzHasFeedback [nzErrorTip]="'必填'">
          <nz-select formControlName="target_service">
            <nz-option *ngFor="let service of targetServices" [nzValue]="service" [nzLabel]="service"></nz-option>
          </nz-select>
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>Target Path</nz-form-label>
        <nz-form-control nzHasFeedback [nzErrorTip]="'必填'">
          <input nz-input formControlName="target_path" />
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
          <nz-select formControlName="concurrency_policy">
            <nz-option *ngFor="let opt of concurrencyPolicies" [nzValue]="opt" [nzLabel]="opt"></nz-option>
          </nz-select>
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>回调Method</nz-form-label>
        <nz-form-control>
          <nz-select formControlName="callback_method">
            <nz-option *ngFor="let m of httpMethods" [nzValue]="m" [nzLabel]="m"></nz-option>
          </nz-select>
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
          <nz-select formControlName="overlap_action">
            <nz-option *ngFor="let opt of overlapActions" [nzValue]="opt" [nzLabel]="opt"></nz-option>
          </nz-select>
        </nz-form-control>
      </nz-form-item>
      <nz-form-item>
        <nz-form-label>Failure Action</nz-form-label>
        <nz-form-control>
          <nz-select formControlName="failure_action">
            <nz-option *ngFor="let opt of failureActions" [nzValue]="opt" [nzLabel]="opt"></nz-option>
          </nz-select>
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

  @if (isArtemisTask) {
    <nz-collapse style="margin-top: 16px; max-width: 1000px;">
      <nz-collapse-panel nzHeader="Artemis task.yaml 配置" [nzActive]="false">
        @if (taskYamlLoading) {
          <p>加载中...</p>
        } @else if (taskYamlSection) {
          <div style="margin-bottom: 8px; color: #999; font-size: 12px;">
            任务代码: <code>{{extractedTaskCode()}}</code> — 仅编辑此任务的 variants 配置
          </div>
          <textarea nz-input [(ngModel)]="taskYamlSection" [rows]="15"
                    style="font-family: monospace; font-size: 12px; width: 100%;"></textarea>
          <div style="margin-top: 8px;">
            <button nz-button nzType="primary" [disabled]="taskYamlSaving" (click)="saveTaskYaml()">
              {{taskYamlSaving ? '保存中...' : '保存 YAML'}}
            </button>
          </div>
        } @else {
          <p style="color: #999;">无法加载 task.yaml 配置</p>
        }
      </nz-collapse-panel>
    </nz-collapse>
  }
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
export class CronjobTaskFormComponent implements OnChanges {
  @Input() api: any;
  @Input() value: Partial<Task> | null = null;
  @Output() save = new EventEmitter<Partial<Task>>();
  @Output() cancel = new EventEmitter<void>();

  concurrencyPolicies = ['PARALLEL','SKIP'];
  overlapActions = ['ALLOW','SKIP','CANCEL_PREV','PARALLEL'];
  failureActions = ['RUN_NEW','SKIP','RETRY'];
  httpMethods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'];
  form = this.fb.nonNullable.group({
    name: ['', [Validators.required, Validators.maxLength(128)]],
    description: [''],
    cron_expr: ['', Validators.required],
    timezone: ['UTC'],
    exec_type: ['SYNC'],
    method: ['GET'], // 新增
    target_service: ['', Validators.required], // 新增
    target_path: ['', Validators.required], // 新增
    headers_json: ['{}'],
    body_template: [''],
    retry_policy_json: ['{}'],
    max_concurrency: [1],
    concurrency_policy: ['PARALLEL'],
    callback_method: ['POST'],
    callback_timeout_sec: [10],
    overlap_action: ['ALLOW'],
    failure_action: ['RUN_NEW'],
    status: ['ENABLED']
  });

  // 下拉选项数据
  targetServices: string[] = [];

  // task.yaml integration
  fullYamlContent = '';       // full task.yaml content (preserved for merge)
  taskYamlSection = '';       // only the matching task's config section
  taskYamlLoading = false;
  taskYamlSaving = false;

  get isArtemisTask(): boolean {
    return this.form.value.target_service === 'artemis';
  }

  constructor(private fb: FormBuilder, private msg: NzMessageService) {}
  ngOnChanges(changes: SimpleChanges){
    if(this.value){
      this.form.patchValue(this.value);
      if (this.value.target_service === 'artemis') {
        this.loadTaskYaml();
      }
    }
  }
  ngOnInit() {
    // 拉取 targetService 列表
    // 这里假设有 CronjobsApiService 注入
    if ((this as any).api && typeof (this as any).api.listClients === 'function') {
      (this as any).api.listClients().subscribe({
        next: (list: string[]) => this.targetServices = list,
        error: () => this.targetServices = ['artemis']
      });
    } else {
      this.targetServices = ['artemis'];
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

  extractedTaskCode(): string {
    const path: string = this.form.value.target_path || '';
    const parts = path.split('/');
    return parts[parts.length - 1] || '';
  }

  private loadTaskYaml() {
    if (!(this as any).api || typeof (this as any).api.getTaskYaml !== 'function') return;
    this.taskYamlLoading = true;
    (this as any).api.getTaskYaml().subscribe({
      next: (resp: {path: string, content: string}) => {
        this.fullYamlContent = resp.content || '';
        this.taskYamlSection = this.extractTaskSection(this.fullYamlContent, this.extractedTaskCode());
        this.taskYamlLoading = false;
      },
      error: () => {
        this.fullYamlContent = '';
        this.taskYamlSection = '';
        this.taskYamlLoading = false;
      }
    });
  }

  saveTaskYaml() {
    if (!(this as any).api || typeof (this as any).api.updateTaskYaml !== 'function') return;
    const merged = this.replaceTaskSection(this.fullYamlContent, this.extractedTaskCode(), this.taskYamlSection);
    if (merged === null) {
      this.msg.error('合并 YAML 失败，请检查格式');
      return;
    }
    this.taskYamlSaving = true;
    (this as any).api.updateTaskYaml(merged).subscribe({
      next: () => {
        this.fullYamlContent = merged;
        this.taskYamlSaving = false;
        this.msg.success('task.yaml 已保存（仅更新了 ' + this.extractedTaskCode() + ' 配置）');
      },
      error: (err: any) => {
        this.taskYamlSaving = false;
        this.msg.error('保存 task.yaml 失败');
        console.error('save task.yaml error', err);
      }
    });
  }

  /**
   * Extract a specific task's config section from the full YAML content.
   * Returns the section from the task name line to the next top-level key (or end of tasks block).
   */
  private extractTaskSection(yaml: string, taskCode: string): string {
    if (!yaml || !taskCode) return '';
    const lines = yaml.split('\n');
    const startIdx = lines.findIndex(l => l.trim() === taskCode + ':');
    if (startIdx === -1) return '';
    // Find where the next top-level key starts (2-space indent at task level)
    let endIdx = lines.length;
    for (let i = startIdx + 1; i < lines.length; i++) {
      // Top-level keys under "tasks:" have 2-space indent and end with ":"
      // The task block ends when we hit another 2-space indented line that's a key
      if (i > startIdx + 1 && lines[i].match(/^  \S/)) {
        endIdx = i;
        break;
      }
    }
    return lines.slice(startIdx, endIdx).join('\n');
  }

  /**
   * Replace a specific task's section in the full YAML with the edited section.
   * Returns the merged full YAML, or null if replacement fails.
   */
  private replaceTaskSection(yaml: string, taskCode: string, newSection: string): string | null {
    if (!yaml || !taskCode) return null;
    const lines = yaml.split('\n');
    const startIdx = lines.findIndex(l => l.trim() === taskCode + ':');
    if (startIdx === -1) return null;
    let endIdx = lines.length;
    for (let i = startIdx + 1; i < lines.length; i++) {
      if (i > startIdx + 1 && lines[i].match(/^  \S/)) {
        endIdx = i;
        break;
      }
    }
    const newLines = newSection.split('\n');
    const merged = [...lines.slice(0, startIdx), ...newLines, ...lines.slice(endIdx)];
    return merged.join('\n');
  }
}
