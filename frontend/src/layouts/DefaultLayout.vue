<template>
  <div class="relative h-screen overflow-hidden md:flex">
    <!-- Mobile Menu -->
    <div class="bg-paper-sidebar text-gray-100 flex justify-between md:hidden shrink-0">
      <router-link to="/" class="block p-4 text-white font-bold">SAA</router-link>
      <button @click="sidebarOpen = !sidebarOpen" class="p-4 focus:outline-none focus:bg-paper-active-link">
        <Bars3Icon class="h-6 w-6" />
      </button>
    </div>

    <!-- Sidebar -->
    <aside :class="{ '-translate-x-full': !sidebarOpen }" class="bg-paper-sidebar text-gray-100 w-64 space-y-2 py-7 px-2 absolute inset-y-0 left-0 transform md:relative md:translate-x-0 transition duration-200 ease-in-out z-20 h-full shrink-0 overflow-y-auto">
      <div @click="() => router.push('/')" class="cursor-pointer text-white flex items-center space-x-2 px-4 mb-2">
        <CubeTransparentIcon class="h-8 w-8"/>
        <span class="text-2xl font-extrabold">SAA</span>
      </div>
      <div class="px-4 my-4">
        <div class="border-t border-white border-opacity-20"></div>
      </div>

      <nav class="space-y-1">
        <!-- Navegação geral -->
        <router-link to="/" class="flex items-center space-x-2 py-2.5 px-4 rounded transition duration-200 hover:bg-paper-active-link hover:text-white">
          <HomeIcon class="h-5 w-5"/><span>Home</span>
        </router-link>

        <!-- ── Módulo SAA ───────────────────────────────────────────── -->
        <div class="px-4 pt-4 pb-1">
          <p class="text-xs font-semibold uppercase text-gray-400 tracking-wider">SAA — Alocação</p>
        </div>

        <router-link to="/saa" class="flex items-center space-x-2 py-2.5 px-4 rounded transition duration-200 hover:bg-paper-active-link hover:text-white">
          <ChartBarIcon class="h-5 w-5"/>
          <span>Dashboard</span>
          <span v-if="saaStore.indicadores.conflitosCriticos > 0"
            class="ml-auto bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
            {{ saaStore.indicadores.conflitosCriticos }}
          </span>
        </router-link>

        <router-link to="/saa/grades" class="flex items-center space-x-2 py-2.5 px-4 rounded transition duration-200 hover:bg-paper-active-link hover:text-white">
          <AcademicCapIcon class="h-5 w-5"/><span>Grades</span>
        </router-link>

        <router-link to="/saa/salas" class="flex items-center space-x-2 py-2.5 px-4 rounded transition duration-200 hover:bg-paper-active-link hover:text-white">
          <BuildingOfficeIcon class="h-5 w-5"/><span>Salas</span>
        </router-link>

        <router-link to="/saa/alocacoes" class="flex items-center space-x-2 py-2.5 px-4 rounded transition duration-200 hover:bg-paper-active-link hover:text-white">
          <ClipboardDocumentListIcon class="h-5 w-5"/><span>Alocações</span>
        </router-link>

        <router-link to="/saa/importar" class="flex items-center space-x-2 py-2.5 px-4 rounded transition duration-200 hover:bg-paper-active-link hover:text-white">
          <ArrowUpTrayIcon class="h-5 w-5"/><span>Importar CSV</span>
        </router-link>

        <router-link to="/saa/historico" class="flex items-center space-x-2 py-2.5 px-4 rounded transition duration-200 hover:bg-paper-active-link hover:text-white">
          <ClockIcon class="h-5 w-5"/><span>Histórico</span>
        </router-link>

        <!-- Divisor -->
        <div class="px-4 pt-4 pb-1">
          <div class="border-t border-white border-opacity-20"></div>
        </div>

        <router-link to="/exemplos" class="flex items-center space-x-2 py-2.5 px-4 rounded transition duration-200 hover:bg-paper-active-link hover:text-white">
          <BeakerIcon class="h-5 w-5"/><span>Exemplos</span>
        </router-link>
        <router-link v-if="authStore.isAuthenticated" to="/pacientes" class="flex items-center space-x-2 py-2.5 px-4 rounded transition duration-200 hover:bg-paper-active-link hover:text-white">
          <UsersIcon class="h-5 w-5"/><span>Pacientes</span>
        </router-link>
        <router-link v-if="authStore.isAdmin" to="/admin" class="flex items-center space-x-2 py-2.5 px-4 rounded transition duration-200 hover:bg-paper-active-link hover:text-white">
          <ShieldCheckIcon class="h-5 w-5"/><span>Admin</span>
        </router-link>
      </nav>
    </aside>

    <!-- Content -->
    <div class="flex-1 flex flex-col bg-paper-bg overflow-y-auto h-full">
      <header class="flex justify-between items-center p-6 bg-white/80 backdrop-blur-md border-b border-gray-300 sticky top-0 z-10">
        <div>
          <h1 class="text-2xl font-semibold text-paper-text">{{ $route.name }}</h1>
        </div>
        <div>
          <router-link v-if="!authStore.isAuthenticated" to="/login">
            <Button variant="primary">
              <template #icon><ArrowRightOnRectangleIcon class="h-5 w-5" /></template>
              Login
            </Button>
          </router-link>
          <ProfileDropdown v-else />
        </div>
      </header>
      <main class="flex-1">
        <div class="container py-4 md:py-6">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  HomeIcon, BeakerIcon, UsersIcon, ShieldCheckIcon,
  CubeTransparentIcon, Bars3Icon, ArrowRightOnRectangleIcon,
  ChartBarIcon, AcademicCapIcon, BuildingOfficeIcon,
  ClipboardDocumentListIcon, ArrowUpTrayIcon, ClockIcon,
} from '@heroicons/vue/24/outline';
import ProfileDropdown from '../components/ProfileDropdown.vue';
import Button from '../components/Button.vue';
import { useAuthStore } from '../stores/auth';
import { useSaaStore } from '../stores/saa';

const sidebarOpen = ref(false);
const route    = useRoute();
const router   = useRouter();
const authStore = useAuthStore();
const saaStore  = useSaaStore();

watch(() => route.path, () => { sidebarOpen.value = false; });
</script>
