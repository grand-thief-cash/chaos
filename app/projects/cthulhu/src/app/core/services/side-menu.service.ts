import {Injectable} from '@angular/core';
import {ActivatedRoute, NavigationEnd, Route, Router} from '@angular/router';
import {filter} from 'rxjs/operators';

export interface SideMenuItem { label: string; route: string; selectedMatchExact?: boolean; }
export interface SideMenuGroup { title: string; icon: string | null; items: SideMenuItem[]; open?: boolean; }

interface MenuGroupMeta { title: string; icon?: string; }
interface MenuItemMeta { label: string; icon?: string; order?: number; hide?: boolean; }

@Injectable({ providedIn: 'root' })
export class SideMenuService {
  private cache: Record<string, SideMenuGroup[]> = {};

  constructor(private router: Router) {
    // 监听路由导航事件（NavigationEnd），每当路由切换完成时，自动调用 rebuildFromActive() 方法，刷新侧边菜单内容。
    // 紧接着，构造函数初始化时也主动调用一次 rebuildFromActive()，确保菜单首次加载时就能正确显示。
    this.router.events.pipe(filter(e => e instanceof NavigationEnd)).subscribe(() => this.rebuildFromActive());
    this.rebuildFromActive();
  }

  getGroups(navKey: string): SideMenuGroup[] {
    return this.cache[navKey] ?? [];
  }

  private rebuildFromActive() {
    // 获取当前路由的 URL，并去除查询参数部分。
    // 提取 URL 的第一个路径段，作为菜单分组的关键。
    const url = this.router.url.split('?')[0];
    const firstSegment = url.split('/')[1];
    if (!firstSegment) return;

    // 查找顶级路径对应的激活路由
    const featureRoute = this.findActivatedChild(this.router.routerState.root, firstSegment);
    if (!featureRoute) return;

    // shell 路由（path: ''）
    const shellRoute = featureRoute.firstChild; // 可能为 cronjobs 的 '' shell
    const shellConfig = shellRoute?.routeConfig; // routeConfig 类型为 Route | null
    if (!shellConfig) return;
    // 获取该路由下的 shell 路由配置和菜单分组元数据。
    const groupMeta: MenuGroupMeta | undefined = (shellConfig.data as any)?.['menuGroup'];
    const children = (shellConfig.children || []) as Route[];

    const items: SideMenuItem[] = [];
    const metaMap: Record<string, MenuItemMeta> = {};
    // 遍历 shell 路由的子路由，收集每个子路由的菜单元数据，过滤掉隐藏项或重定向项。
    for (const child of children) {
      const meta: MenuItemMeta | undefined = (child.data as any)?.['menu'];
      if (!child.path || !meta || meta.hide) continue; // 跳过重定向或隐藏
      metaMap[child.path] = meta;
      items.push({ label: meta.label, route: `/${firstSegment}/${child.path}`, selectedMatchExact: true });
    }
    // 按菜单项的顺序进行排序。
    items.sort((a, b) => {
      const ap = a.route.split('/').pop()!;
      const bp = b.route.split('/').pop()!;
      return (metaMap[ap]?.order ?? 0) - (metaMap[bp]?.order ?? 0);
    });
    // 如果有有效的分组元数据和菜单项，则将其缓存到 cache 中，供菜单组件使用。
    if (groupMeta && items.length) {
      this.cache[firstSegment] = [ { title: groupMeta.title, icon: groupMeta.icon || null, open: true, items } ];
    }
  }

  private findActivatedChild(root: ActivatedRoute, segment: string): ActivatedRoute | null {
    for (const child of root.children) {
      const path = child.routeConfig?.path;
      if (path === segment) return child;
      const deeper = this.findActivatedChild(child, segment);
      if (deeper) return deeper;
    }
    return null;
  }
}
