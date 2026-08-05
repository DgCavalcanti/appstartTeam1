import { createRouter, createWebHistory } from 'vue-router';
import SaaImportacao from '../views/SaaImportacao.vue';
import SaaHistorico from '../views/SaaHistorico.vue';
import SaaCenario from '../views/SaaCenario.vue';
import SaaVisualizacao from '../views/SaaVisualizacao.vue';
import SaaPadroes from '../views/SaaPadroes.vue';

const routes = [
  // A importação é a porta de entrada do processo (etapa 1).
  { path: '/', redirect: '/saa/importacao' },
  { path: '/saa/importacao', name: 'Importação', component: SaaImportacao },
  { path: '/saa/historico', name: 'Histórico', component: SaaHistorico },
  { path: '/saa/padroes', name: 'Padrões', component: SaaPadroes },
  { path: '/saa/cenarios/:id', name: 'Cenário', component: SaaCenario },
  { path: '/saa/cenarios/:id/visualizacao', name: 'Visualização', component: SaaVisualizacao },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  linkActiveClass: 'bg-paper-active-link',
  linkExactActiveClass: 'bg-paper-active-link',
});

export default router;
