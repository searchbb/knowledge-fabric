import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'
import WorkspacePage from '../pages/WorkspacePage/WorkspacePage.vue'
import RegistryPage from '../pages/RegistryPage/RegistryPage.vue'
import OverviewPage from '../pages/OverviewPage/OverviewPage.vue'
import AutoPipelinePage from '../pages/AutoPipelinePage/AutoPipelinePage.vue'
import ThemeHubPage from '../pages/ThemeViewPage/ThemeViewPage.vue'
import ThemeDetailPage from '../pages/ThemeDetailPage/ThemeDetailPage.vue'
import ConceptDetailPage from '../pages/ConceptDetailPage/ConceptDetailPage.vue'
import RelationListPage from '../pages/RelationListPage/RelationListPage.vue'
import RelationDetailPage from '../pages/RelationDetailPage/RelationDetailPage.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true
  },
  {
    path: '/workspace/:projectId/:section?',
    name: 'Workspace',
    component: WorkspacePage,
    props: true
  },
  {
    path: '/workspace/overview',
    name: 'Overview',
    component: OverviewPage,
    meta: {
      runtimeSurface: 'global',
      productStatus: 'phase2',
    },
  },
  {
    path: '/workspace/registry',
    name: 'Registry',
    component: RegistryPage,
    meta: {
      runtimeSurface: 'global',
      productStatus: 'phase2',
    },
  },
  {
    path: '/workspace/themes',
    name: 'ThemeHub',
    component: ThemeHubPage,
    meta: {
      runtimeSurface: 'global',
      productStatus: 'phase2',
    },
  },
  {
    path: '/workspace/themes/:themeId',
    name: 'ThemeDetail',
    component: ThemeDetailPage,
    props: true,
    meta: {
      runtimeSurface: 'global',
      productStatus: 'phase2',
    },
  },
  {
    path: '/workspace/entry/:entryId',
    name: 'ConceptDetail',
    component: ConceptDetailPage,
    props: true,
    meta: {
      runtimeSurface: 'global',
      productStatus: 'phase2',
    },
  },
  {
    path: '/workspace/relations',
    name: 'RelationList',
    component: RelationListPage,
    meta: {
      runtimeSurface: 'global',
      productStatus: 'phase2',
    },
  },
  {
    path: '/workspace/relations/:relationId',
    name: 'RelationDetail',
    component: RelationDetailPage,
    props: true,
    meta: {
      runtimeSurface: 'global',
      productStatus: 'phase2',
    },
  },
  {
    path: '/workspace/auto',
    name: 'AutoPipeline',
    component: AutoPipelinePage,
    meta: {
      runtimeSurface: 'global',
      productStatus: 'phase2',
    },
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true,
    meta: {
      runtimeSurface: 'legacy_zep',
      productStatus: 'legacy',
    },
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true,
    meta: {
      runtimeSurface: 'legacy_zep',
      productStatus: 'legacy',
    },
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true,
    meta: {
      runtimeSurface: 'legacy_zep',
      productStatus: 'legacy',
    },
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true,
    meta: {
      runtimeSurface: 'legacy_zep',
      productStatus: 'legacy',
    },
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
