import {Routes} from '@angular/router';
import {AtlasShellComponent} from './pages/atlas-shell.component';
import {AtlasOverviewComponent} from './pages/atlas-overview.component';
import {ExtractionRunsComponent} from './pages/extraction-runs.component';
import {SemanticGovernanceComponent} from './pages/semantic-governance.component';
import {CrosswalkComponent} from './pages/crosswalk.component';
import {GraphQueryComponent} from './pages/graph-query.component';
import {CompanyReviewComponent} from './pages/company-review.component';
import {EntityReviewComponent} from './pages/entity-review.component';
import {SampleRunsComponent} from './pages/sample-runs.component';
import {SampleExtractionsComponent} from './pages/sample-extractions.component';
import {environment} from '../../../environments/environment';

const DEVELOPMENT_SAMPLING_ROUTES: Routes = environment.atlasSamplingEnabled ? [
  {path:'sample-runs', component:SampleRunsComponent, data:{breadcrumb:'Sample Runs',menu:{label:'Sample Runs',order:2,group:'概览与采样'}}},
  {path:'sample-extractions', component:SampleExtractionsComponent, data:{breadcrumb:'Sample Extractions',menu:{label:'Sample Extractions',order:3,group:'概览与采样'}}},
] : [];

export const ATLAS_ROUTES: Routes = [{
  path: '', component: AtlasShellComponent,
  data: {breadcrumb: 'Atlas', menuGroup: {title: 'Atlas', icon: 'share-alt'}},
  children: [
    {path:'', redirectTo:'overview', pathMatch:'full'},
    // 概览与采样: land + discovery phase
    {path:'overview', component:AtlasOverviewComponent, data:{breadcrumb:'Overview',menu:{label:'Overview',order:1,group:'概览与采样'}}},
    ...DEVELOPMENT_SAMPLING_ROUTES,
    // 语义治理: review discovered semantics before production
    {path:'semantics', component:SemanticGovernanceComponent, data:{breadcrumb:'Semantic Governance',menu:{label:'Semantic Governance',order:4,group:'语义治理'}}},
    {path:'crosswalk', component:CrosswalkComponent, data:{breadcrumb:'Industry Crosswalk',menu:{label:'Industry Crosswalk',order:5,group:'语义治理'}}},
    // 正式运行: production extraction + entity curation
    {path:'extractions', component:ExtractionRunsComponent, data:{breadcrumb:'Extraction Runs',menu:{label:'Extraction Runs',order:6,group:'正式运行'}}},
    {path:'entities', component:EntityReviewComponent, data:{breadcrumb:'Entity Review',menu:{label:'Entity Review',order:7,group:'正式运行'}}},
    // 查询与审核: graph query + company review
    {path:'graph', component:GraphQueryComponent, data:{breadcrumb:'Graph Query',menu:{label:'Graph & Query',order:8,group:'查询与审核'}}},
    {path:'company-review', component:CompanyReviewComponent, data:{breadcrumb:'Company Review',menu:{label:'Company Review',order:9,group:'查询与审核'}}}
  ]
}];
