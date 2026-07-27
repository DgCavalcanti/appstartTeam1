<template>
  <transition name="fade">
    <div v-if="isLoading" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex flex-col items-center justify-center gap-4">
      <div class="relative">
        <div class="w-14 h-14 rounded-full border-4 border-paper-primary/20"></div>
        <div class="absolute inset-0 w-14 h-14 rounded-full border-4 border-transparent border-t-paper-primary animate-spin"></div>
      </div>
      <p class="text-white text-sm font-medium animate-pulse">Carregando…</p>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { useUiStore } from '../stores/ui';
import { storeToRefs } from 'pinia';

const uiStore = useUiStore();
const { isLoading } = storeToRefs(uiStore);
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
