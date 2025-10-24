import {Injectable} from '@angular/core';
import {ActivatedRoute, NavigationEnd, Router} from '@angular/router';
import {BehaviorSubject} from 'rxjs';
import {filter} from 'rxjs/operators';

export interface BreadcrumbItem { label: string; url: string; }

@Injectable({ providedIn: 'root' })
export class BreadcrumbService {
  private readonly breadcrumbsSub = new BehaviorSubject<BreadcrumbItem[]>([]);
  readonly breadcrumbs$ = this.breadcrumbsSub.asObservable();

// 1. 构造函数监听路由变化（NavigationEnd），每次路由变化时调用 build 方法生成面包屑。
  constructor(private router: Router, private activatedRoute: ActivatedRoute) {
    this.router.events.pipe(filter(e => e instanceof NavigationEnd)).subscribe(() => {
      const crumbs = this.build(this.activatedRoute.root);
      this.breadcrumbsSub.next(crumbs);
    });
  }

  // 2. build 方法递归遍历 ActivatedRoute 的子路由，根据每个路由的 data.breadcrumb 属性和路径拼接生成面包屑项（BreadcrumbItem）。
  // 3. 生成的面包屑数组通过 BehaviorSubject 发布，外部可通过 breadcrumbs$ 订阅获取最新面包屑数据。
  private build(route: ActivatedRoute, url: string = '', acc: BreadcrumbItem[] = []): BreadcrumbItem[] {
    const children = route.children;
    if (!children || children.length === 0) return acc;
    for (const child of children) {
      const routeURL = child.snapshot.url.map(s => s.path).join('/');
      const nextUrl = routeURL ? `${url}/${routeURL}` : url;
      const label = child.snapshot.data['breadcrumb'];
      if (label) acc.push({ label, url: nextUrl });
      this.build(child, nextUrl, acc);
    }
    return acc;
  }
}
