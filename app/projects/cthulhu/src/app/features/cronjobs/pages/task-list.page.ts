import {Component, OnInit, ViewChild, ElementRef, signal} from '@angular/core';
import {CommonModule} from '@angular/common';
import {CronjobsStore} from '../state/cronjobs.store';
import {Router, RouterLink} from '@angular/router';
import {NzTableModule} from 'ng-zorro-antd/table';
import {NzButtonModule} from 'ng-zorro-antd/button';
import {NzBadgeModule} from 'ng-zorro-antd/badge';
import {NzPopconfirmModule} from 'ng-zorro-antd/popconfirm';
import {NzPaginationModule} from 'ng-zorro-antd/pagination';
import {NzInputModule} from 'ng-zorro-antd/input';
import {NzSelectModule} from 'ng-zorro-antd/select';
import {FormsModule} from '@angular/forms';
import {NzMessageModule, NzMessageService} from 'ng-zorro-antd/message';
import {NzDropDownModule} from 'ng-zorro-antd/dropdown';
import {NzModalModule, NzModalService} from 'ng-zorro-antd/modal';
import {forkJoin} from 'rxjs';
import {CronjobsApiService} from '../services/cronjobs-api.service';

@Component({
  selector: 'cron-task-list-page',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, NzTableModule, NzButtonModule, NzBadgeModule, NzPopconfirmModule, NzPaginationModule, NzInputModule, NzSelectModule, NzMessageModule, NzDropDownModule, NzModalModule],
  template: `
  <div *ngIf="store.loadingTasks(); else listTpl" class="loading">加载中...</div>
  <ng-template #listTpl>
    <div class="header">
      <h2>定时任务列表</h2>
      <div class="actions">
        <button nz-button nzType="default" (click)="reload()">刷新</button>
        <button nz-button nzType="default" (click)="toggleFilters()">{{showFilters? '收起筛选':'展开筛选'}}</button>
        <button nz-button nzType="default" (click)="refreshCache()">刷新缓存</button>
        <button nz-button nzType="default" nz-dropdown [nzDropdownMenu]="opsMenu">操作<span class="sel-count" *ngIf="selectedCount()"> ({{selectedCount()}})</span></button>
        <nz-dropdown-menu #opsMenu="nzDropdownMenu">
          <ul nz-menu>
            <li nz-menu-item (click)="onImport()">导入</li>
            <li nz-menu-item (click)="onExportSelected()">导出 (勾选 {{selectedCount()}})</li>
            <li nz-menu-item (click)="onEnableSelected()">启用 (勾选 {{selectedCount()}})</li>
            <li nz-menu-item (click)="onTriggerSelected()">触发 (勾选 {{selectedCount()}})</li>
            <li nz-menu-divider></li>
            <li nz-menu-item (click)="onExportAll()">全部导出</li>
            <li nz-menu-item (click)="onEnableAll()">全部启用</li>
          </ul>
        </nz-dropdown-menu>
        <input #fileInput type="file" (change)="onFileSelect($event)" style="display: none" accept=".json">
        <button nz-button nzType="primary" [routerLink]="['/cronjobs/tasks','new']">新建任务</button>
      </div>
    </div>
    <div class="filters" *ngIf="showFilters">
      <div class="filter-grid">
        <div class="f-item">
          <label>名称</label>
          <input nz-input placeholder="模糊匹配" [(ngModel)]="search" />
        </div>
        <div class="f-item">
          <label>描述</label>
          <input nz-input placeholder="模糊匹配" [(ngModel)]="desc" />
        </div>
        <div class="f-item">
          <label>状态</label>
          <nz-select [(ngModel)]="status" nzAllowClear nzPlaceHolder="全部" style="width:100%">
            <nz-option nzValue="ALL" nzLabel="全部"></nz-option>
            <nz-option nzValue="ENABLED" nzLabel="启用"></nz-option>
            <nz-option nzValue="DISABLED" nzLabel="禁用"></nz-option>
          </nz-select>
        </div>
        <div class="f-item wide">
          <label>创建时间</label>
          <div class="range">
            <input nz-input type="datetime-local" [(ngModel)]="createdFrom" />
            <span class="dash">-</span>
            <input nz-input type="datetime-local" [(ngModel)]="createdTo" />
          </div>
        </div>
        <div class="f-item wide">
          <label>更新时间</label>
            <div class="range">
              <input nz-input type="datetime-local" [(ngModel)]="updatedFrom" />
              <span class="dash">-</span>
              <input nz-input type="datetime-local" [(ngModel)]="updatedTo" />
            </div>
        </div>
      </div>
      <div class="filter-actions">
        <button nz-button nzType="primary" (click)="apply()">查询</button>
        <button nz-button nzType="default" (click)="clearFilters()">重置</button>
      </div>
    </div>
    <nz-table [nzData]="store.pagedTasks()" nzBordered *ngIf="store.pagedTasks().length; else emptyTpl">
      <thead>
        <tr>
          <th class="chk"><input type="checkbox" [checked]="allOnPageChecked()" [indeterminate]="someOnPageChecked()" (change)="toggleAllOnPage($event)"></th>
          <th [nzShowSort]="true" [nzSortOrder]="sortOrder('id')" (nzSortOrderChange)="onSort('id',$event)">ID</th>
          <th [nzShowSort]="true" [nzSortOrder]="sortOrder('name')" (nzSortOrderChange)="onSort('name',$event)">名称</th>
          <th>Cron</th>
          <th>状态</th>
          <th>并发</th>
          <th [nzShowSort]="true" [nzSortOrder]="sortOrder('created_at')" (nzSortOrderChange)="onSort('created_at',$event)">创建时间</th>
          <th [nzShowSort]="true" [nzSortOrder]="sortOrder('updated_at')" (nzSortOrderChange)="onSort('updated_at',$event)">更新时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr *ngFor="let t of store.pagedTasks()">
          <td class="chk"><input type="checkbox" [checked]="isSelected(t.id)" (change)="toggleRow(t.id, $event)"></td>
          <td>{{t.id}}</td>
          <td><a [routerLink]="['/cronjobs/tasks', t.id]">{{t.name}}</a><div class="desc" *ngIf="t.description">{{t.description}}</div></td>
          <td>{{t.cron_expr}}</td>
          <td>
            <nz-badge [nzStatus]="t.status==='ENABLED' ? 'success' : 'default'" [nzText]="t.status==='ENABLED'?'启用':'禁用'"></nz-badge>
          </td>
          <td>{{t.max_concurrency}}</td>
          <td>{{t.created_at | date:'yyyy-MM-dd HH:mm:ss'}}</td>
          <td>{{t.updated_at | date:'yyyy-MM-dd HH:mm:ss'}}</td>
          <td class="ops">
            <button nz-button nzSize="small" (click)="toggle(t)">{{t.status==='ENABLED'?'禁用':'启用'}}</button>
            <button nz-button nzSize="small" (click)="trigger(t)">触发</button>
            <button nz-button nzSize="small" [routerLink]="['/cronjobs/tasks', t.id, 'edit']">编辑</button>
            <button nz-button nzSize="small" (click)="clone(t)">基于此创建</button>
            <button nz-button nzSize="small" nzDanger nz-popconfirm nzPopconfirmTitle="确认删除该任务?" (nzOnConfirm)="remove(t)">删除</button>
          </td>
        </tr>
      </tbody>
    </nz-table>
    <ng-template #emptyTpl><div class="empty">暂无任务</div></ng-template>
    <div class="pager" *ngIf="store.taskTotal() > 0">
      <nz-pagination [nzTotal]="store.taskTotal()" [nzPageIndex]="store.taskPageIndex()" [nzPageSize]="store.taskPageSize()"
        (nzPageIndexChange)="onPage($event)" (nzPageSizeChange)="onPageSize($event)" [nzShowSizeChanger]="true" [nzPageSizeOptions]="[50,100,150,200]"></nz-pagination>
    </div>
  </ng-template>
  `,
  styles: [`
    .header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
    .actions { display:flex; gap:8px; flex-wrap:wrap; }
    .ops { display:flex; gap:4px; flex-wrap:wrap; }
    .chk { width: 32px; text-align: center; }
    .sel-count { color: #888; font-weight: normal; font-size: 12px; }
    .empty { padding: 32px; text-align:center; color:#888; }
    .pager { margin-top: 16px; display:flex; justify-content:center; }
    .filters { border:1px solid #eee; padding:12px; border-radius:6px; margin-bottom: 12px; display:flex; flex-direction:column; gap:12px; }
    .filter-grid { display:grid; grid-template-columns: repeat(auto-fill,minmax(220px,1fr)); gap:12px 16px; }
    .f-item { display:flex; flex-direction:column; gap:4px; }
    .f-item.wide { grid-column: span 2; min-width: 440px; }
    @media (max-width: 820px){ .f-item.wide { grid-column: span 1; min-width:unset; } }
    .f-item label { font-size:12px; color:#555; font-weight:500; }
    .range { display:flex; align-items:center; gap:4px; }
    .range input { flex:1; }
    .dash { color:#999; }
    .filter-actions { display:flex; gap:8px; }
  `]
})
export class TaskListPageComponent implements OnInit {
  search = '';
  desc = '';
  status = 'ALL';
  createdFrom = '';
  createdTo = '';
  updatedFrom = '';
  updatedTo = '';
  showFilters = true;
  selected = signal<number[]>([]);
  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;
  constructor(public store: CronjobsStore, private msg: NzMessageService, private modal: NzModalService, private router: Router, private api: CronjobsApiService) {}
  ngOnInit(){ this.store.loadTasks(); }
  toggleFilters(){ this.showFilters = !this.showFilters; }
  reload(){ this.store.loadTasks(true); }
  toggle(t: any){
    const obs = t.status==='ENABLED'? this.store.disable(t.id): this.store.enable(t.id);
    obs.subscribe(()=> this.store.loadTasks(true));
  }
  trigger(t: any){ this.store.trigger(t.id).subscribe(()=> this.store.loadRuns(t.id, true)); }
  refreshCache(){ this.store.refreshCache().subscribe(()=> this.store.loadTasks(true)); }
  remove(t: any){ this.store.delete(t.id).subscribe({ next: ()=> { this.msg.success('删除成功');
    this.store.loadTasks(true); }, error: ()=> this.msg.error('删除失败'), }); }
  onPage(i: number){ this.store.setTaskPage(i); }
  onPageSize(size: number){ this.store.setTaskPageSize(size); }
  // Sort is server-side (paging is backend-driven, so the current page alone
  // can't be sorted). ng-zorro cycles ascend->descend->null; collapse null to
  // asc for a clean 2-state toggle with no "unsorted" state. Default: id asc.
  sortOrder(by: string): 'ascend'|'descend'|null {
    if(this.store.taskSortBy() !== by) return null;
    return this.store.taskSortOrder() === 'asc' ? 'ascend' : 'descend';
  }
  onSort(by: string, order: 'ascend'|'descend'|string|null){
    const mapped: 'asc'|'desc' = order === 'descend' ? 'desc' : 'asc';
    this.store.setTaskSort(by, mapped);
  }
  apply(){
    this.store.applyFilters({
      name: this.search,
      desc: this.desc,
      status: this.status as any,
      createdFrom: this.toRFC3339(this.createdFrom),
      createdTo: this.toRFC3339(this.createdTo),
      updatedFrom: this.toRFC3339(this.updatedFrom),
      updatedTo: this.toRFC3339(this.updatedTo)
    });
  }
  clearFilters(){
    this.search=''; this.desc=''; this.status='ALL'; this.createdFrom=''; this.createdTo=''; this.updatedFrom=''; this.updatedTo='';
    this.store.resetFilters();
  }
  clone(t: any){
    // 过滤掉不应复制的字段（保持与当前 Task model / API 字段一致）
    const allowedKeys = [
      'name','description','cron_expr','timezone','exec_type',
      // target 相关（新字段）
      'method','target_service','target_path',
      // 请求体/策略
      'headers_json','body_template','timeout_seconds','retry_policy_json',
      'max_concurrency','concurrency_policy',
      // callback / 行为
      'callback_method','callback_timeout_sec','overlap_action','failure_action',
      'status'
    ];
    const template: any = {};
    for(const k of allowedKeys){
      if (t[k] !== undefined) template[k] = t[k];
    }
    // 名称附加后缀避免重复
    if(template.name) template.name = template.name + ' copy';
    // 状态统一初始为 ENABLED
    template.status = 'ENABLED';
    // 导航状态传递模板
    this.router.navigate(['/cronjobs/tasks','new'], { state: { template } });
  }
  onImport() { this.fileInput.nativeElement.click(); }

  // ── selection ── persisted across pages (a Set-like array held in a signal
  // so template bindings update on change).
  isSelected(id: number){ return this.selected().includes(id); }
  selectedCount(){ return this.selected().length; }
  private pageIds(): number[] { return (this.store.pagedTasks() || []).map((t:any)=> t.id); }
  allOnPageChecked(): boolean {
    const ids = this.pageIds();
    const sel = this.selected();
    return ids.length > 0 && ids.every(id => sel.includes(id));
  }
  someOnPageChecked(): boolean {
    const ids = this.pageIds();
    const sel = this.selected();
    return ids.some(id => sel.includes(id)) && !this.allOnPageChecked();
  }
  toggleRow(id: number, ev: Event){
    const checked = (ev.target as HTMLInputElement).checked;
    const cur = this.selected();
    this.selected.set(checked ? [...cur, id] : cur.filter(x => x !== id));
  }
  toggleAllOnPage(ev: Event){
    const checked = (ev.target as HTMLInputElement).checked;
    const pageIds = this.pageIds();
    const rest = this.selected().filter(id => !pageIds.includes(id));
    this.selected.set(checked ? [...rest, ...pageIds] : rest);
  }
  onFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    // 读取文件内容
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        const data = JSON.parse(content);

        // 调用后端 API 导入
        this.api.importTasks(file).subscribe({
          next: (res) => {
            if (res.failed_count === 0) {
              this.msg.success(`成功导入 ${res.success_count} 个任务`);
            } else {
              this.msg.warning(`成功导入 ${res.success_count} 个任务，失败 ${res.failed_count} 个`);
              console.error('Import failed tasks:', res.failed_tasks);
            }
            this.store.loadTasks(true);
          },
          error: (err) => {
            this.msg.error('导入失败: ' + err.message);
            console.error('Import error:', err);
          }
        });
      } catch (err) {
        this.msg.error('文件格式错误，请上传有效的 JSON 文件');
      }
    };
    reader.readAsText(file);
    // 重置 input 以便再次选择同一文件
    input.value = '';
  }
  // ── 操作 menu handlers ── 导出/启用/触发 operate on the selection; 全部**
  // ignore it. Trigger has no "全部" variant (triggering every task at once
  // would be destructive), so it loops the single-task endpoint for the
  // selected set only.
  onExportSelected(){
    const ids = this.selected();
    if(!ids.length){ this.msg.warning('请先勾选要导出的任务'); return; }
    this.downloadExport(undefined, ids);
  }
  onExportAll(){ this.downloadExport(); }
  onEnableSelected(){
    const ids = this.selected();
    if(!ids.length){ this.msg.warning('请先勾选要启用的任务'); return; }
    this.runBatchEnable(ids);
  }
  onEnableAll(){
    this.modal.confirm({
      nzTitle: '全部启用',
      nzContent: '确认启用所有任务？将启用全部定时任务（忽略勾选）。',
      nzOkText: '全部启用',
      nzOkType: 'primary',
      nzCancelText: '取消',
      nzOnOk: () => this.runBatchEnable([])
    });
  }
  onTriggerSelected(){
    const ids = this.selected();
    if(!ids.length){ this.msg.warning('请先勾选要触发的任务'); return; }
    this.modal.confirm({
      nzTitle: '触发任务',
      nzContent: `确认触发选中的 ${ids.length} 个任务？将立即为每个任务创建一次运行。`,
      nzOkText: '触发',
      nzOkType: 'primary',
      nzCancelText: '取消',
      nzOnOk: () => this.runBatchTrigger(ids)
    });
  }
  private downloadExport(taskId?: number, ids?: number[]){
    this.api.exportTasks(taskId, ids).subscribe({
      next: blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `tasks_export_${new Date().toISOString().slice(0,10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        this.msg.success('导出成功');
      },
      error: err => this.msg.error('导出失败: ' + (err.message||''))
    });
  }
  private runBatchEnable(ids: number[]){
    this.api.batchEnable(ids).subscribe({
      next: res => {
        const m = res.failed ? `启用 ${res.success} 个，失败 ${res.failed} 个` : `启用 ${res.success} 个`;
        res.failed ? this.msg.warning(m) : this.msg.success(m);
        this.store.loadTasks(true);
      },
      error: () => this.msg.error('批量启用失败')
    });
  }
  private runBatchTrigger(ids: number[]){
    // Frontend loop reuses the single-task trigger endpoint so snapshot fill,
    // concurrency policy, and trace propagation all stay server-side.
    forkJoin(ids.map(id => this.api.triggerTask(id))).subscribe({
      next: () => { this.msg.success(`已触发 ${ids.length} 个任务`); this.store.loadTasks(true); },
      error: err => { this.msg.error('部分触发失败: ' + (err.message||'')); this.store.loadTasks(true); }
    });
  }
  private toRFC3339(local: string): string | undefined {
    if(!local) return undefined;
    const d = new Date(local);
    if (isNaN(d.getTime())) return undefined;
    return d.toISOString();
  }
}
