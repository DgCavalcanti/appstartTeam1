import { createRouter, createWebHistory, NavigationGuardNext } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import Home from '../views/Home.vue';
import Login from '../views/Login.vue';
import Admin from '../views/Admin.vue';
import Exemplos from '../views/Exemplos.vue';
import Pacientes from '../views/Pacientes.vue';

// ── Módulo SAA ────────────────────────────────────────────────────────────
import SaaDashboard from '../views/SaaDashboard.vue';
import SaaGrades    from '../views/SaaGrades.vue';
import SaaSalas     from '../views/SaaSalas.vue';
import SaaAlocacoes from '../views/SaaAlocacoes.vue';
import SaaImportar  from '../views/SaaImportar.vue';
import SaaHistorico from '../views/SaaHistorico.vue';

const routes = [
  { path: '/',       name: 'Home',      component: Home },
  { path: '/login',  name: 'Login',     component: Login, meta: { layout: 'LoginLayout' } },
  { path: '/admin',  name: 'Admin',     component: Admin, meta: { requiresAuth: true } },
  { path: '/exemplos', name: 'Exemplos', component: Exemplos },
  { path: '/pacientes', name: 'Pacientes', component: Pacientes, meta: { requiresAuth: true } },

  // ── SAA: Sistema de Apoio à Alocação ─────────────────────────────────
  { path: '/saa',             name: 'SAA Dashboard', component: SaaDashboard },
  { path: '/saa/grades',      name: 'SAA Grades',    component: SaaGrades },
  { path: '/saa/salas',       name: 'SAA Salas',     component: SaaSalas },
  { path: '/saa/alocacoes',   name: 'SAA Alocações', component: SaaAlocacoes },
  { path: '/saa/importar',    name: 'SAA Importar',  component: SaaImportar },
  { path: '/saa/historico',   name: 'SAA Histórico', component: SaaHistorico },
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
