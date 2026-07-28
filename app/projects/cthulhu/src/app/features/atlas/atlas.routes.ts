import {Routes} from '@angular/router';
import {AtlasShellComponent} from './pages/atlas-shell.component';
import {AtlasOverviewComponent} from './pages/atlas-overview.component';
import {ExtractionRunsComponent} from './pages/extraction-runs.component';
import {SemanticGovernanceComponent} from './pages/semantic-governance.component';
import {CrosswalkComponent} from './pages/crosswalk.component';
import {GraphQueryComponent} from './pages/graph-query.component';
import {CompanyReviewComponent} from './pages/company-review.component';
import {EntityReviewComponent} from './pages/entity-review.component';

export const ATLAS_ROUTES: Routes = [{
  path: '', component: AtlasShellComponent,
  data: {breadcrumb: 'Atlas', menuGroup: {title: 'Atlas', icon: 'share-alt'}},
  children: [
    {path:'', redirectTo:'overview', pathMatch:'full'},
    {path:'overview', component:AtlasOverviewComponent, data:{breadcrumb:'Overview',menu:{label:'Overview',order:1}}},
    {path:'extractions', component:ExtractionRunsComponent, data:{breadcrumb:'Extraction Runs',menu:{label:'Extraction Runs',order:2}}},
    {path:'semantics', component:SemanticGovernanceComponent, data:{breadcrumb:'Semantic Governance',menu:{label:'Semantic Governance',order:3}}},
    {path:'crosswalk', component:CrosswalkComponent, data:{breadcrumb:'Industry Crosswalk',menu:{label:'Industry Crosswalk',order:4}}},
    {path:'entities', component:EntityReviewComponent, data:{breadcrumb:'Entity Review',menu:{label:'Entity Review',order:5}}},
    {path:'graph', component:GraphQueryComponent, data:{breadcrumb:'Graph Query',menu:{label:'Graph & Query',order:6}}},
    {path:'company-review', component:CompanyReviewComponent, data:{breadcrumb:'Company Review',menu:{label:'Company Review',order:7}}}
  ]
}];
