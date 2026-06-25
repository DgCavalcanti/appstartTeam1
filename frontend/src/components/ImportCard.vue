<template>
  <div class="bg-white rounded-lg shadow-paper p-6">
    <div class="flex items-center gap-3 mb-3">
      <component :is="icone" class="h-6 w-6 text-paper-primary" />
      <h3 class="font-semibold text-paper-text">{{ titulo }}</h3>
    </div>
    <p class="text-xs text-gray-400 mb-4">{{ descricao }}</p>

    <!-- Área de upload via drag-and-drop ou clique -->
    <div
      class="border-2 border-dashed rounded-lg p-6 text-center transition-colors"
      :class="[
        carregando ? 'cursor-not-allowed opacity-75 border-gray-200' : 'cursor-pointer',
        !carregando && arrastando ? 'border-paper-primary bg-blue-50' : '',
        !carregando && !arrastando ? 'border-gray-200 hover:border-paper-primary' : '',
      ]"
      @dragover.prevent="!carregando && (arrastando = true)"
      @dragleave="arrastando = false"
      @drop.prevent="onDrop"
      @click="!carregando && fileInput?.click()"
    >
      <!-- CORRIGIDO (auditoria técnica): não havia nenhum indicador visual
           enquanto o arquivo era enviado/processado — o card ficava parado,
           parecendo travado, até o resultado chegar. Mostra um spinner
           "rodando" (como em sites comuns) enquanto a importação está em
           andamento, sem remover o aviso de resultado abaixo. -->
      <template v-if="carregando">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-paper-primary mx-auto mb-2"></div>
        <p class="text-sm text-gray-500">Processando <code class="font-mono">{{ arquivo }}</code>…</p>
        <p class="text-xs text-gray-400 mt-1">Aguarde até a importação terminar</p>
      </template>
      <template v-else>
        <ArrowUpTrayIcon class="h-8 w-8 mx-auto mb-2 text-gray-300" />
        <p class="text-sm text-gray-500">Arraste o <code class="font-mono">{{ arquivo }}</code> aqui</p>
        <p class="text-xs text-gray-400 mt-1">ou clique para selecionar</p>
      </template>
      <input ref="fileInput" type="file" accept=".csv" class="hidden" :disabled="carregando" @change="onFileChange" />
    </div>

    <!-- Feedback do resultado (mantido — o spinner acima é exibido enquanto
         uma nova importação está em andamento, e este aviso continua
         aparecendo com o resultado da última importação concluída) -->
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

const props = defineProps<{
  titulo: string;
  arquivo: string;
  descricao: string;
  icone: any;
  resultado: { ok: boolean; mensagem: string } | null;
  /** Exibe o spinner de "processando" enquanto a importação está em andamento. */
  carregando?: boolean;
}>();

const emit = defineEmits<{ importar: [arquivo: File] }>();

const arrastando = ref(false);
const fileInput  = ref<HTMLInputElement | null>(null);

function onFileChange(e: Event) {
  if (props.carregando) return;
  const file = (e.target as HTMLInputElement).files?.[0];
  if (file) emit('importar', file);
}

function onDrop(e: DragEvent) {
  if (props.carregando) return;
  arrastando.value = false;
  const file = e.dataTransfer?.files?.[0];
  if (file) emit('importar', file);
}
</script>
