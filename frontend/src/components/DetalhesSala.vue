<template>
  <div>
    <!-- Informações gerais -->
    <div class="grid grid-cols-2 gap-4 text-sm mb-6">
      <div><span class="font-medium text-gray-600">Número:</span> {{ sala.numero }}</div>
      <div><span class="font-medium text-gray-600">Bloco:</span> {{ sala.bloco }}</div>
      <div><span class="font-medium text-gray-600">Andar:</span> {{ sala.andar || '—' }}</div>
      <div>
        <span class="font-medium text-gray-600">Status:</span>
        <span class="ml-2 px-2 py-0.5 rounded-full text-xs font-medium" :class="badgeStatus(sala.status)">
          {{ sala.status }}
        </span>
      </div>
      <div><span class="font-medium text-gray-600">Especialidade Pref.:</span> {{ sala.especialidade_preferencial || '—' }}</div>
      <div><span class="font-medium text-gray-600">Acessível:</span> {{ sala.acessibilidade ? 'Sim' : 'Não' }}</div>
      <div class="col-span-2">
        <span class="font-medium text-gray-600">Equipamentos:</span>
        <span v-if="sala.equipamentos.length === 0" class="ml-2 text-gray-400">Nenhum</span>
        <span v-else class="ml-2 flex flex-wrap gap-1 inline-flex">
          <span v-for="eq in sala.equipamentos" :key="eq" class="px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-xs">{{ eq }}</span>
        </span>
      </div>
    </div>

    <!-- Alocações da sala -->
    <div class="mb-6">
      <h3 class="font-semibold text-gray-700 mb-2">Alocações nesta Sala</h3>
      <div v-if="alocacoesDaSala.length === 0" class="text-sm text-gray-400">Nenhuma alocação.</div>
      <div v-else class="space-y-2">
        <div
          v-for="aloc in alocacoesDaSala"
          :key="aloc.id"
          class="text-sm p-2 bg-gray-50 rounded border border-gray-100"
        >
          <span class="font-medium">{{ store.getGrade(aloc.grade_id)?.especialidade ?? aloc.grade_id }}</span>
          — {{ store.getGrade(aloc.grade_id)?.profissional ?? '' }}
          — {{ aloc.dia_semana }} / {{ aloc.turno }}
        </div>
      </div>
    </div>

    <!-- Conflitos vinculados -->
    <div>
      <h3 class="font-semibold text-gray-700 mb-2 flex items-center gap-2">
        <ExclamationTriangleIcon class="h-4 w-4 text-red-500" />
        Conflitos ({{ conflitosLocalSala.length }})
      </h3>
      <div v-if="conflitosLocalSala.length === 0" class="text-sm text-green-600">
        ✓ Nenhum conflito identificado nesta sala.
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="c in conflitosLocalSala"
          :key="c.id"
          class="text-sm p-2 rounded border"
          :class="c.gravidade === 'critico' ? 'bg-red-50 border-red-200 text-red-700' : 'bg-yellow-50 border-yellow-200 text-yellow-800'"
        >
          <span class="font-bold uppercase text-xs mr-2">{{ c.gravidade }}</span>
          {{ c.descricao }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { ExclamationTriangleIcon } from '@heroicons/vue/24/outline';
import { useSaaStore, type Sala, type Alocacao } from '../stores/saa';

const props = defineProps<{ sala: Sala }>();
defineEmits(['fechar']);

const store = useSaaStore();

const alocacoesDaSala  = computed(() => store.alocacoes.filter((a: Alocacao) => a.sala_id === props.sala.id));
const conflitosLocalSala = computed(() => store.getConflitosParaSala(props.sala.id));

function badgeStatus(status: string) {
  switch (status) {
    case 'disponivel': return 'bg-green-100 text-green-700';
    case 'bloqueada':  return 'bg-red-100 text-red-700';
    case 'reforma':
    case 'manutencao': return 'bg-yellow-100 text-yellow-700';
    case 'ocupada':    return 'bg-blue-100 text-blue-700';
    default:           return 'bg-gray-100 text-gray-700';
  }
}
</script>
