import {Injectable} from '@angular/core';
import {ActivatedRoute, NavigationEnd, Route, Router} from '@angular/router';
import {filter} from 'rxjs/operators';

export interface SideMenuItem {
  label: string;
  route?: string;
  selectedMatchExact?: boolean;
  order?: number;
  group?: string;
  children?: SideMenuItem[];
}

export interface SideMenuGroup {
  title: string;
  icon: string | null;
  items: SideMenuItem[];
  open?: boolean;
}

interface MenuGroupMeta { title: string; icon?: string; }
interface MenuItemMeta { label: string; icon?: string; order?: number; group?: string; hide?: boolean; }

@Injectable({ providedIn: 'root' })
export class SideMenuService {
  private cache: Record<string, SideMenuGroup[]> = {};

  constructor(private router: Router) {
    this.router.events.pipe(filter(e => e instanceof NavigationEnd)).subscribe(() => this.rebuildFromActive());
    this.rebuildFromActive();
  }

  getGroups(navKey: string): SideMenuGroup[] {
    return this.cache[navKey] ?? [];
  }

  private rebuildFromActive() {
    const url = this.router.url.split('?')[0];
    const firstSegment = url.split('/')[1];
    if (!firstSegment) return;

    const featureRoute = this.findActivatedChild(this.router.routerState.root, firstSegment);
    if (!featureRoute) return;

    const shellRoute = featureRoute.firstChild;
    const shellConfig = shellRoute?.routeConfig;
    if (!shellConfig) return;

    const groupMeta: MenuGroupMeta | undefined = (shellConfig.data as any)?.['menuGroup'];
    const children = (shellConfig.children || []) as Route[];
    const items = children
      .map(child => this.buildMenuItem(firstSegment, '', child))
      .filter((item): item is SideMenuItem => !!item)
      .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

    const grouped = this.groupBySubGroup(items);
    if (groupMeta && grouped.length) {
      this.cache[firstSegment] = [{ title: groupMeta.title, icon: groupMeta.icon || null, open: true, items: grouped }];
    }
  }

  /**
   * Cluster items that declare a `group` into nested sub-menus (one nz-submenu
   * per group). Items without a group stay flat. Group sub-menus are ordered by
   * the smallest order of their children so the overall sort is preserved.
   */
  private groupBySubGroup(items: SideMenuItem[]): SideMenuItem[] {
    const withGroup = items.filter(i => i.group);
    if (!withGroup.length) return items;
    const withoutGroup = items.filter(i => !i.group);
    const order: string[] = [];
    const buckets: Record<string, SideMenuItem[]> = {};
    for (const item of withGroup) {
      const g = item.group as string;
      if (!buckets[g]) {
        buckets[g] = [];
        order.push(g);
      }
      buckets[g].push(item);
    }
    const subMenus: SideMenuItem[] = order.map(g => ({
      label: g,
      order: Math.min(...buckets[g].map(i => i.order ?? 0)),
      children: buckets[g],
    }));
    subMenus.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
    return [...withoutGroup, ...subMenus];
  }

  private buildMenuItem(firstSegment: string, parentPath: string, route: Route): SideMenuItem | null {
    const meta: MenuItemMeta | undefined = (route.data as any)?.['menu'];
    if (!route.path || !meta || meta.hide) return null;

    const fullPath = parentPath ? `${parentPath}/${route.path}` : route.path;
    const children = ((route.children || []) as Route[])
      .map(child => this.buildMenuItem(firstSegment, fullPath, child))
      .filter((item): item is SideMenuItem => !!item)
      .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

    return {
      label: meta.label,
      route: `/${firstSegment}/${fullPath}`,
      selectedMatchExact: !children.length,
      order: meta.order ?? 0,
      group: meta.group,
      children: children.length ? children : undefined,
    };
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
