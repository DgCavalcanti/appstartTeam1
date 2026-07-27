<template>
  <div class="relative h-screen overflow-hidden md:flex">
    <!-- Menu mobile -->
    <div class="bg-paper-sidebar text-gray-100 flex justify-between md:hidden shrink-0">
      <router-link to="/" class="block p-4 text-white font-bold">SAA</router-link>
      <button @click="sidebarOpen = !sidebarOpen" class="p-4 focus:outline-none focus:bg-paper-active-link">
        <Bars3Icon class="h-6 w-6" />
      </button>
    </div>

    <!-- Barra lateral -->
    <aside
      :class="{ '-translate-x-full': !sidebarOpen }"
      class="bg-paper-sidebar text-gray-100 w-64 space-y-2 py-7 px-2 absolute inset-y-0 left-0 transform md:relative md:translate-x-0 transition duration-200 ease-in-out z-20 h-full shrink-0 overflow-y-auto"
    >
      <div @click="() => router.push('/')" class="cursor-pointer text-white flex items-center space-x-2 px-4 mb-2 group">
        <CubeTransparentIcon class="h-8 w-8 transition-transform duration-300 group-hover:rotate-12" />
        <span class="text-2xl font-extrabold tracking-tight">SAA</span>
      </div>
      <div class="px-4 my-4">
        <div class="border-t border-white border-opacity-20"></div>
      </div>

      <!--
        As 6 etapas do processo entram aqui como stepper quando a máquina de
        estados existir. Por ora só a etapa 1 está construída.
      -->
      <nav class="space-y-1">
        <div class="px-4 pt-1 pb-2">
          <p class="text-xs font-semibold uppercase text-gray-400 tracking-wider">Processo</p>
        </div>

        <router-link
          to="/saa/importacao"
          class="sidebar-link flex items-center space-x-2 py-2.5 px-4 rounded transition-all duration-200 hover:bg-paper-active-link hover:text-white relative"
        >
          <span class="sidebar-indicator absolute left-0 top-1/2 -translate-y-1/2 w-1 h-0 bg-paper-primary rounded-r transition-all duration-200"></span>
          <ArrowUpTrayIcon class="h-5 w-5" />
          <span>1 — Importação</span>
        </router-link>

        <div class="px-4 pt-4 pb-1">
          <div class="border-t border-white border-opacity-20"></div>
        </div>

        <router-link
          to="/saa/padroes"
          class="sidebar-link flex items-center space-x-2 py-2.5 px-4 rounded transition-all duration-200 hover:bg-paper-active-link hover:text-white relative"
        >
          <span class="sidebar-indicator absolute left-0 top-1/2 -translate-y-1/2 w-1 h-0 bg-paper-primary rounded-r transition-all duration-200"></span>
          <Cog6ToothIcon class="h-5 w-5" />
          <span>Padrões</span>
        </router-link>
      </nav>

      <!-- Sidebar footer -->
      <div class="absolute bottom-0 left-0 right-0 px-4 py-3 border-t border-white/10">
        <p class="text-[10px] text-gray-500 text-center">SAA v1.0</p>
      </div>
    </aside>

    <!-- Conteúdo -->
    <div class="flex-1 flex flex-col bg-paper-bg overflow-y-auto h-full">
      <header class="flex items-center p-6 bg-white/80 backdrop-blur-md border-b border-gray-200 sticky top-0 z-10">
        <div class="flex items-center gap-2">
          <div class="w-1.5 h-6 bg-paper-primary rounded-full"></div>
          <h1 class="text-2xl font-semibold text-paper-text">{{ route.name }}</h1>
        </div>
      </header>
      <main class="flex-1">
        <div class="container py-4 md:py-6">
          <router-view v-slot="{ Component }">
            <transition name="route" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ArrowUpTrayIcon, Bars3Icon, Cog6ToothIcon, CubeTransparentIcon } from '@heroicons/vue/24/outline';

const sidebarOpen = ref(false);
const route = useRoute();
const router = useRouter();

watch(() => route.path, () => { sidebarOpen.value = false; });
</script>

<style scoped>
/* Active sidebar link indicator */
.sidebar-link.router-link-active .sidebar-indicator,
.sidebar-link.router-link-exact-active .sidebar-indicator {
  height: 60%;
}
</style>
