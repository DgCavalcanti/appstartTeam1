import { createRouter, createWebHistory, NavigationGuardNext } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import Home from '../views/Home.vue';
import Login from '../views/Login.vue';
import Admin from '../views/Admin.vue';
import Exemplos from '../views/Exemplos.vue';
import Pacientes from '../views/Pacientes.vue';

// ── Módulo SAA ────────────────────────────────────────────────────────────
import SaaDashboard    from '../views/SaaDashboard.vue';
import SaaGrades       from '../views/SaaGrades.vue';
import SaaSalas        from '../views/SaaSalas.vue';
import SaaAlocacoes    from '../views/SaaAlocacoes.vue';
import SaaImportar     from '../views/SaaImportar.vue';
import SaaHistorico    from '../views/SaaHistorico.vue';
import SaaCapacidade   from '../views/SaaCapacidade.vue';
import SaaConsultas    from '../views/SaaConsultas.vue';
import SaaQualidadeDados from '../views/SaaQualidadeDados.vue';

const routes = [
  { path: '/',       name: 'Início',      component: Home },
  { path: '/login',  name: 'Login',     component: Login, meta: { layout: 'LoginLayout' } },
  { path: '/admin',  name: 'Administração',     component: Admin, meta: { requiresAuth: true } },
  { path: '/exemplos', name: 'Exemplos', component: Exemplos },
  { path: '/pacientes', name: 'Pacientes', component: Pacientes, meta: { requiresAuth: true } },

  // ── SAA: Sistema de Apoio à Alocação ─────────────────────────────────
  { path: '/saa',           name: 'Painel SAA', component: SaaDashboard, meta: { requiresAuth: true } },
  { path: '/saa/grades',    name: 'SAA Grades',    component: SaaGrades,    meta: { requiresAuth: true } },
  { path: '/saa/salas',     name: 'SAA Salas',     component: SaaSalas,     meta: { requiresAuth: true } },
  { path: '/saa/alocacoes', name: 'SAA Alocações', component: SaaAlocacoes, meta: { requiresAuth: true } },
  { path: '/saa/importar',  name: 'SAA Importar',  component: SaaImportar,  meta: { requiresAuth: true } },
  { path: '/saa/historico', name: 'SAA Histórico', component: SaaHistorico, meta: { requiresAuth: true } },

  // ── AGHU: Dados reais ─────────────────────────────────────────────────
  { path: '/saa/capacidade',      name: 'Capacidade AGHU',  component: SaaCapacidade,    meta: { requiresAuth: true } },
  { path: '/saa/consultas',       name: 'Consultas AGHU',   component: SaaConsultas,     meta: { requiresAuth: true } },
  { path: '/saa/qualidade-dados', name: 'Qualidade de Dados', component: SaaQualidadeDados, meta: { requiresAuth: true } },

  // ── Fallback: qualquer rota desconhecida volta para a Home ────────────
  { path: '/:pathMatch(.*)*', name: 'NotFound', redirect: '/' },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  linkActiveClass: 'bg-paper-active-link',
  linkExactActiveClass: 'bg-paper-active-link',
});

router.beforeEach((to, _from, next: NavigationGuardNext) => {
  const authStore = useAuthStore();
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'Login' });
  } else {
    next();
  }
});

export default router;
