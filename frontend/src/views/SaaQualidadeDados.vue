<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-paper-text">Qualidade dos Dados</h1>
      <p class="text-sm text-gray-500 mt-1">
        Problemas detectados nos arquivos importados.
        Corrija-os para garantir a confiabilidade dos indicadores.
      </p>
      <p class="text-sm text-gray-500 mt-2 flex items-center gap-1">
        Para importar ou substituir arquivos, acesse
        <router-link to="/saa/importar" class="underline font-medium">Importar Dados</router-link>.
      </p>
    </div>

    <!-- Alerta de erro -->
    <div v-if="store.erro" class="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex gap-2">
      <ExclamationTriangleIcon class="h-4 w-4 shrink-0 mt-0.5" />
      {{ store.erro }}
    </div>

    <!-- Carregando -->
    <div v-if="store.carregando" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-paper-primary"></div>
    </div>

    <!-- Resumo numérico -->
    <div v-if="store.qualidade && !store.carregando" class="grid grid-cols-3 gap-4 mb-6">
      <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
        <div class="text-3xl font-bold text-gray-700">
          {{ store.qualidade.total_problemas }}
        </div>
        <div class="text-xs text-gray-500 mt-1">Total de Problemas</div>
      </div>
      <div class="bg-white rounded-lg p-4 border border-red-100 text-center">
        <div class="text-3xl font-bold text-red-600">
          {{ store.qualidade.criticos }}
        </div>
        <div class="text-xs text-gray-500 mt-1">Críticos</div>
      </div>
      <div class="bg-white rounded-lg p-4 border border-green-100 text-center">
        <div class="text-3xl font-bold text-green-600">
          {{ store.qualidade.total_problemas === 0 ? '✓' : store.qualidade.total_problemas - store.qualidade.criticos }}
        </div>
        <div class="text-xs text-gray-500 mt-1">
          {{ store.qualidade.total_problemas === 0 ? 'Nenhum problema' : 'Avisos / Atenção' }}
        </div>
      </div>
    </div>

    <!-- Tudo ok -->
    <div v-if="store.qualidade && store.qualidade.total_problemas === 0 && !store.carregando"
      class="bg-green-50 border border-green-200 rounded-lg p-6 text-center text-green-700">
      <CheckCircleIcon class="h-10 w-10 mx-auto mb-2 text-green-500" />
      <p class="font-medium">Nenhum problema detectado nos dados importados.</p>
    </div>

    <!-- Lista de problemas -->
    <div v-if="store.qualidade && store.qualidade.problemas.length > 0 && !store.carregando"
      class="space-y-3">
      <div
        v-for="(p, i) in store.qualidade.problemas"
        :key="i"
        :class="[
          'bg-white rounded-lg border p-4 flex items-start gap-3',
          p.gravidade === 'critico' ? 'border-red-200' :
          p.gravidade === 'atencao' ? 'border-yellow-200' : 'border-gray-200'
        ]"
      >
        <!-- Ícone de gravidade -->
        <div :class="[
          'shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold mt-0.5',
          p.gravidade === 'critico' ? 'bg-red-500' :
          p.gravidade === 'atencao' ? 'bg-yellow-400' : 'bg-gray-300'
        ]">
          {{ p.gravidade === 'critico' ? '!' : p.gravidade === 'atencao' ? '⚠' : 'i' }}
        </div>

        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xs font-semibold uppercase tracking-wide text-gray-400">
              {{ p.categoria }}
            </span>
            <span :class="[
              'text-xs px-2 py-0.5 rounded-full font-medium',
              p.gravidade === 'critico' ? 'bg-red-100 text-red-700' :
              p.gravidade === 'atencao' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'
            ]">
              {{ labelGravidade(p.gravidade) }}
            </span>
          </div>
          <p class="text-sm text-gray-700">{{ p.descricao }}</p>
          <p class="text-xs text-gray-400 mt-0.5">
            {{ p.quantidade.toLocaleString('pt-BR') }} registro(s) afetado(s)
          </p>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { ExclamationTriangleIcon, CheckCircleIcon } from '@heroicons/vue/24/outline';
import { useAghuStore } from '../stores/aghu';

const store = useAghuStore();

function labelGravidade(g: string): string {
  if (g === 'critico') return 'Crítico';
  if (g === 'atencao') return 'Atenção';
  return 'Aviso';
}

onMounted(() => store.buscarQualidade());
</script>
