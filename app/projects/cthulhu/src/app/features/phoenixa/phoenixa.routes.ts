import {Routes} from '@angular/router';
import {PhoenixAShellComponent} from './phoenixa.component';
import {BufferStatsComponent, DataCatalogComponent, TableDetailComponent} from './pages';

export const PHOENIXA_ROUTES: Routes = [
  {
    path: '',
    component: PhoenixAShellComponent,
    data: { breadcrumb: 'PhoenixA', menuGroup: { title: 'PhoenixA', icon: 'database' } },
    children: [
      { path: '', redirectTo: 'catalog', pathMatch: 'full' },
      {
        path: 'catalog',
        data: { breadcrumb: 'Data Catalog', menu: { label: 'Data Catalog', order: 1 } },
        children: [
          { path: '', component: DataCatalogComponent },
          { path: ':schema/:table', component: TableDetailComponent, data: { breadcrumb: 'Table Detail' } }
        ]
      },
      { path: 'buffer', component: BufferStatsComponent, data: { breadcrumb: 'Write Buffer', menu: { label: 'Write Buffer', order: 2 } } }
    ]
  }
];



