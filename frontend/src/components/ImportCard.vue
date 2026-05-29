<template>
  <div class="bg-white rounded-lg shadow-paper p-6">
    <div class="flex items-center gap-3 mb-3">
      <component :is="icone" class="h-6 w-6 text-paper-primary" />
      <h3 class="font-semibold text-paper-text">{{ titulo }}</h3>
    </div>
    <p class="text-xs text-gray-400 mb-4">{{ descricao }}</p>

    <!-- Área de upload via drag-and-drop ou clique -->
    <div
      class="border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors"
      :class="arrastando ? 'border-paper-primary bg-blue-50' : 'border-gray-200 hover:border-paper-primary'"
      @dragover.prevent="arrastando = true"
      @dragleave="arrastando = false"
      @drop.prevent="onDrop"
      @click="fileInput?.click()"
    >
      <ArrowUpTrayIcon class="h-8 w-8 mx-auto mb-2 text-gray-300" />
      <p class="text-sm text-gray-500">Arraste o <code class="font-mono">{{ arquivo }}</code> aqui</p>
      <p class="text-xs text-gray-400 mt-1">ou clique para selecionar</p>
      <input ref="fileInput" type="file" accept=".csv" class="hidden" @change="onFileChange" />
    </div>

    <!-- Feedback do resultado -->
    <div v-if="resultado" class="mt-3 flex items-center gap-2 text-sm rounded p-2"
      :class="resultado.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'">
      <CheckCircleIcon v-if="resultado.ok" class="h-4 w-4 shrink-0" />
      <ExclamationTriangleIcon v-else class="h-4 w-4 shrink-0" />
      {{ resultado.mensagem }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ArrowUpTrayIcon, CheckCircleIcon, ExclamationTriangleIcon } from '@heroicons/vue/24/outline';

defineProps<{
  titulo: string;
  arquivo: string;
  descricao: string;
  icone: any;
  resultado: { ok: boolean; mensagem: string } | null;
}>();

const emit = defineEmits<{ importar: [csv: string] }>();

const arrastando = ref(false);
const fileInput  = ref<HTMLInputElement | null>(null);

function lerArquivo(file: File) {
  const reader = new FileReader();
  reader.onload = (e) => emit('importar', e.target?.result as string);
  reader.readAsText(file, 'UTF-8');
}

function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (file) lerArquivo(file);
}

function onDrop(e: DragEvent) {
  arrastando.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (file) lerArquivo(file);
}
</script>
