import {CommonModule} from '@angular/common';
import {Component, inject} from '@angular/core';
import {FormsModule} from '@angular/forms';
import {AtlasApiService} from '../services/atlas-api.service';

@Component({
  selector:'app-atlas-graph-query', standalone:true, imports:[CommonModule,FormsModule],
  template:`<section class="page"><h1>Graph 与知识查询</h1>
    <div><input class="wide" [(ngModel)]="search" placeholder="实体名称 / 别名"><button (click)="find()">查实体</button></div>
    <pre *ngIf="searchResult">{{searchResult | json}}</pre>
    <h2>LLM 受控查询</h2><textarea [(ngModel)]="question" rows="4"></textarea>
    <button (click)="ask()">查询</button><pre *ngIf="answer">{{answer | json}}</pre>
    <small>Agent 只能调用 search_entities、neighborhood、claims、security profile 和 financial metrics；不能执行 Cypher 或写库。</small>
  </section>`,
  styles:[`.page{padding:24px}.wide,textarea{width:min(720px,80%);padding:8px}textarea{display:block;margin-bottom:8px}
    button{margin-left:8px;padding:8px 14px}pre{background:#fafafa;padding:14px;max-height:360px;overflow:auto}small{color:#666}`]
})
export class GraphQueryComponent {
  private api=inject(AtlasApiService); search=''; question=''; searchResult:any; answer:any;
  find(){this.api.entities(this.search).subscribe(v=>this.searchResult=v);}
  ask(){this.api.ask(this.question).subscribe(v=>this.answer=v);}
}
