<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-paper-text">Histórico de Ajustes</h1>
      <p class="text-sm text-gray-500">Registro de todas as alterações manuais realizadas nas alocações.</p>
    </div>

    <Card>
      <div v-if="store.historico.length === 0" class="text-center text-gray-400 py-12">
        <ClockIcon class="h-12 w-12 mx-auto mb-3 opacity-30" />
        <p>Nenhum ajuste registrado ainda. As alterações manuais aparecerão aqui automaticamente.</p>
      </div>
      <div v-else class="space-y-4">
        <div
          v-for="reg in store.historico"
          :key="reg.id"
          class="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
        >
          <div class="flex flex-wrap items-start justify-between gap-2 mb-2">
            <div>
              <span class="font-semibold text-paper-text">Alocação #{{ reg.alocacao_id }}</span>
              <span class="ml-3 text-sm text-gray-500">por <strong>{{ reg.usuario }}</strong></span>
            </div>
            <span class="text-xs text-gray-400">{{ reg.data_hora }}</span>
          </div>
          <div class="flex items-center gap-2 text-sm mb-2">
            <span class="px-2 py-0.5 rounded bg-gray-100 text-gray-700">
              Sala {{ store.getSala(reg.sala_anterior_id)?.numero ?? reg.sala_anterior_id }}
            </span>
            <ArrowRightIcon class="h-4 w-4 text-gray-400" />
            <span class="px-2 py-0.5 rounded bg-paper-primary text-white">
              Sala {{ store.getSala(reg.sala_nova_id)?.numero ?? reg.sala_nova_id }}
            </span>
          </div>
          <div class="flex flex-wrap gap-3 text-xs">
            <span v-if="reg.conflitos_antes.length > 0" class="text-red-600">
              Antes: {{ reg.conflitos_antes.length }} conflito(s)
            </span>
            <span v-else class="text-green-600">Antes: sem conflitos</span>
            <span v-if="reg.conflitos_depois.length > 0" class="text-orange-600">
              Depois: {{ reg.conflitos_depois.length }} conflito(s)
            </span>
            <span v-else class="text-green-600">Depois: sem conflitos</span>
          </div>
          <div v-if="reg.justificativa" class="mt-2 text-sm text-gray-600 bg-yellow-50 border border-yellow-200 rounded p-2">
            <span class="font-medium">Justificativa:</span> {{ reg.justificativa }}
          </div>
        </div>
      </div>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { ClockIcon, ArrowRightIcon } from '@heroicons/vue/24/outline';
import { useSaaStore } from '../stores/saa';
import Card from '../components/Card.vue';

const store = useSaaStore();
</script>
