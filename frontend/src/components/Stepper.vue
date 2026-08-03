<template>
  <nav class="bg-white rounded-lg border border-paper-line shadow-paper p-4">
    <ol class="flex flex-wrap gap-2">
      <li v-for="(etapa, idx) in etapas" :key="etapa.numero" class="flex-1 min-w-[8.5rem] flex items-stretch">
        <button
          class="w-full text-left px-3 py-2 rounded border transition-all duration-200"
          :class="classes(etapa)"
          @click="$emit('ir', etapa.numero)"
        >
          <div class="flex items-center gap-2">
            <span
              class="w-6 h-6 shrink-0 rounded-full text-xs font-bold flex items-center justify-center transition-all duration-200"
              :class="classesDoNumero(etapa)"
            >
              <svg v-if="etapa.status === 'preenchida'" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              <span v-else>{{ etapa.numero }}</span>
            </span>
            <span class="text-xs font-medium truncate">{{ curto(etapa.nome) }}</span>
          </div>
          <p class="text-[11px] mt-1 ml-8" :class="classesDoSelo(etapa)">
            {{ selo(etapa.status) }}
          </p>
        </button>
        <!-- Connector line between steps -->
        <div
          v-if="idx < etapas.length - 1"
          class="hidden md:flex items-center px-1"
        >
          <div class="w-3 h-0.5 rounded-full" :class="etapa.status === 'preenchida' ? 'bg-paper-success' : 'bg-gray-200'"></div>
        </div>
      </li>
    </ol>

    <p v-if="algumaDesatualizada" class="mt-3 text-sm text-paper-text bg-paper-warning/10 border border-paper-warning/30 rounded p-3">
      Alguma coisa mudou depois que a alocação foi feita, então ela pode não valer
      mais. O resultado continua guardado — refaça a etapa 5 quando quiser.
    </p>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue';

export interface EtapaResumo {
  numero: number;
  chave: string;
  nome: string;
  status: 'pendente' | 'preenchida' | 'desatualizada';
  atual: boolean;
}

const props = defineProps<{ etapas: EtapaResumo[] }>();
defineEmits<{ (e: 'ir', numero: number): void }>();

const algumaDesatualizada = computed(() =>
  props.etapas.some(e => e.status === 'desatualizada')
);

const SELOS: Record<string, string> = {
  pendente: 'Pendente',
  preenchida: 'Preenchida',
  desatualizada: 'Desatualizada',
};

function selo(status: string): string {
  return SELOS[status] ?? status;
}

/** O nome completo não cabe no cartão; o essencial é a primeira ideia. */
function curto(nome: string): string {
  return nome.replace(/ (do|da|de|manuais da) .*/, '');
}

function classes(etapa: EtapaResumo): string {
  if (etapa.atual) return 'border-paper-primary bg-paper-primary/10 text-paper-text shadow-sm';
  return 'border-gray-200 hover:border-gray-300 hover:shadow-sm text-paper-text';
}

function classesDoNumero(etapa: EtapaResumo): string {
  if (etapa.status === 'preenchida') return 'bg-paper-success text-white';
  if (etapa.status === 'desatualizada') return 'bg-paper-warning text-white';
  return 'bg-gray-200 text-gray-500';
}

function classesDoSelo(etapa: EtapaResumo): string {
  if (etapa.status === 'preenchida') return 'text-paper-success';
  if (etapa.status === 'desatualizada') return 'text-paper-warning';
  return 'text-gray-400';
}
</script>
