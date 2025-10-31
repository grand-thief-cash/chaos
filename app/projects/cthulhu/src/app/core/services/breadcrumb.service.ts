import {Injectable} from '@angular/core';
import {ActivatedRoute, NavigationEnd, Router} from '@angular/router';
import {BehaviorSubject} from 'rxjs';
import {filter} from 'rxjs/operators';

export interface BreadcrumbItem { label: string; url: string; }

@Injectable({ providedIn: 'root' })
export class BreadcrumbService {
  private readonly breadcrumbsSub = new BehaviorSubject<BreadcrumbItem[]>([]);
  readonly breadcrumbs$ = this.breadcrumbsSub.asObservable();

  constructor(private router: Router, private activatedRoute: ActivatedRoute) {
    this.router.events.pipe(filter(e => e instanceof NavigationEnd)).subscribe(() => {
      const crumbs = this.buildActiveChain(this.activatedRoute.root);
      this.breadcrumbsSub.next(crumbs);
    });
  }

  private buildActiveChain(route: ActivatedRoute, url: string = '', acc: BreadcrumbItem[] = [], seen: Set<string> = new Set()): BreadcrumbItem[] {
    const routeURL = route.snapshot.url.map(s => s.path).join('/');
    const nextUrl = routeURL ? (url ? `${url}/${routeURL}` : `/${routeURL}`) : url || '/';
    const label = route.snapshot.data['breadcrumb'];
    if (label) {
      const crumbUrl = nextUrl || '/';
      const key = `${label}|${crumbUrl}`;
      if (!seen.has(key)) {
        acc.push({ label, url: crumbUrl });
        seen.add(key);
      }
    }
    // 只沿激活的 primary outlet 继续
    const child = route.firstChild;
    if (child) this.buildActiveChain(child, nextUrl, acc, seen);
    return acc;
  }
}
