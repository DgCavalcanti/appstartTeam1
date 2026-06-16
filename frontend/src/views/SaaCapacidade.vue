<template>
  <div>
    <!-- Cabeçalho -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-paper-text">Capacidade Ambulatorial (AGHU)</h1>
      <p class="text-sm text-gray-500 mt-1">
        Indicadores calculados a partir dos dados reais exportados do AGHU.
        Consultas excedentes são registros além da capacidade planejada.
      </p>
    </div>

    <!-- Alerta sem dados -->
    <div v-if="erro" class="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
      <ExclamationTriangleIcon class="h-5 w-5 shrink-0" />
      <span class="text-sm">{{ erro }}</span>
    </div>

    <!-- Cards principais -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
        <div class="text-3xl font-bold text-paper-primary">
          {{ fmt(capacidade?.total_consultas) }}
        </div>
        <div class="text-xs text-gray-500 mt-1">Total de Consultas</div>
      </div>
      <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
        <div class="text-3xl font-bold text-blue-600">
          {{ fmt(capacidade?.consultas_marcadas) }}
        </div>
        <div class="text-xs text-gray-500 mt-1">Marcadas</div>
      </div>
      <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
        <div class="text-3xl font-bold text-green-600">
          {{ fmt(capacidade?.vagas_livres) }}
        </div>
        <div class="text-xs text-gray-500 mt-1">Vagas Livres</div>
      </div>
      <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
        <div class="text-3xl font-bold text-red-600">
          {{ fmt(capacidade?.consultas_excedentes) }}
        </div>
        <div class="text-xs text-gray-500 mt-1">Excedentes</div>
      </div>
    </div>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
        <div class="text-2xl font-bold text-gray-700">
          {{ fmt(capacidade?.bloqueios) }}
        </div>
        <div class="text-xs text-gray-500 mt-1">Bloqueios</div>
      </div>
      <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
        <div class="text-2xl font-bold text-indigo-600">
          {{ pct(capacidade?.taxa_ocupacao) }}
        </div>
        <div class="text-xs text-gray-500 mt-1">Taxa de Ocupação</div>
      </div>
      <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
        <div class="text-2xl font-bold text-orange-500">
          {{ pct(capacidade?.taxa_excedente) }}
        </div>
        <div class="text-xs text-gray-500 mt-1">Taxa de Excedente</div>
      </div>
      <div class="bg-white rounded-lg p-4 border border-gray-200 text-center">
        <div class="text-2xl font-bold text-gray-700">
          {{ fmt(capacidade?.total_grades_ativas) }}
        </div>
        <div class="text-xs text-gray-500 mt-1">Grades Ativas</div>
      </div>
    </div>

    <!-- Carregando -->
    <div v-if="carregando" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-paper-primary"></div>
    </div>

    <!-- Tabela por especialidade -->
    <div v-if="!carregando && porEspecialidade.length > 0" class="bg-white rounded-lg border border-gray-200 overflow-hidden mb-6">
      <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <h2 class="font-semibold text-paper-text">Por Especialidade</h2>
        <span class="text-xs text-gray-400">{{ porEspecialidade.length }} especialidades</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th class="px-4 py-2 text-left">Especialidade</th>
              <th class="px-4 py-2 text-right">Total</th>
              <th class="px-4 py-2 text-right">Marcadas</th>
              <th class="px-4 py-2 text-right">Livres</th>
              <th class="px-4 py-2 text-right">Bloqueios</th>
              <th class="px-4 py-2 text-right">Excedentes</th>
              <th class="px-4 py-2 text-right">Ocupação</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in porEspecialidadeFiltrado"
              :key="row.especialidade"
              class="border-t border-gray-50 hover:bg-gray-50 transition-colors"
            >
              <td class="px-4 py-2 font-medium text-gray-800">{{ row.especialidade }}</td>
              <td class="px-4 py-2 text-right text-gray-600">{{ fmt(row.total_consultas) }}</td>
              <td class="px-4 py-2 text-right text-blue-600 font-medium">{{ fmt(row.marcadas) }}</td>
              <td class="px-4 py-2 text-right text-green-600">{{ fmt(row.livres) }}</td>
              <td class="px-4 py-2 text-right text-gray-500">{{ fmt(row.bloqueios) }}</td>
              <td class="px-4 py-2 text-right text-red-600">{{ fmt(row.excedentes) }}</td>
              <td class="px-4 py-2 text-right">
                <span
                  :class="[
                    'font-semibold',
                    row.taxa_ocupacao >= 0.9 ? 'text-red-600' :
                    row.taxa_ocupacao >= 0.7 ? 'text-orange-500' : 'text-green-600'
                  ]"
                >{{ pct(row.taxa_ocupacao) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- Filtro de busca rápida -->
      <div class="px-4 py-3 border-t border-gray-100">
        <input
          v-model="filtroEsp"
          type="text"
          placeholder="Filtrar por especialidade..."
          class="w-full text-sm border border-gray-200 rounded px-3 py-1.5 focus:outline-none focus:border-paper-primary"
        />
      </div>
    </div>

    <!-- Mapa dia × turno -->
    <div v-if="!carregando && porDiaTurno.length > 0" class="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div class="px-4 py-3 border-b border-gray-100">
        <h2 class="font-semibold text-paper-text">Por Dia × Turno</h2>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th class="px-4 py-2 text-left">Dia</th>
              <th class="px-4 py-2 text-left">Turno</th>
              <th class="px-4 py-2 text-right">Marcadas</th>
              <th class="px-4 py-2 text-right">Livres</th>
              <th class="px-4 py-2 text-right">Bloqueios</th>
              <th class="px-4 py-2 text-right">Excedentes</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in porDiaTurno"
              :key="`${row.dia_semana}-${row.turno}`"
              class="border-t border-gray-50 hover:bg-gray-50 transition-colors"
            >
              <td class="px-4 py-2 font-medium text-gray-800">{{ row.dia_semana }}</td>
              <td class="px-4 py-2 text-gray-600">{{ row.turno }}</td>
              <td class="px-4 py-2 text-right text-blue-600 font-medium">{{ fmt(row.consultas_marcadas) }}</td>
              <td class="px-4 py-2 text-right text-green-600">{{ fmt(row.vagas_livres) }}</td>
              <td class="px-4 py-2 text-right text-gray-500">{{ fmt(row.bloqueios) }}</td>
              <td class="px-4 py-2 text-right text-red-600">{{ fmt(row.excedentes) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { ExclamationTriangleIcon } from '@heroicons/vue/24/outline';
import { useAghuStore } from '../stores/aghu';

const store = useAghuStore();
// storeToRefs preserva a reatividade: sem isso, capacidade/porEspecialidade/
// porDiaTurno/carregando/erro eram "congelados" no valor que tinham no
// instante da desestruturação (antes mesmo do onMounted buscar os dados),
// e a tela nunca refletia novas importações.
const { capacidade, porEspecialidade, porDiaTurno, carregando, erro } = storeToRefs(store);

const filtroEsp = ref('');

const porEspecialidadeFiltrado = computed(() =>
  filtroEsp.value
    ? store.porEspecialidade.filter((r: any) =>
        r.especialidade.toLowerCase().includes(filtroEsp.value.toLowerCase())
      )
    : store.porEspecialidade
);

function fmt(v: number | null | undefined): string {
  if (v == null) return '—';
  return v.toLocaleString('pt-BR');
}

function pct(v: number | null | undefined): string {
  if (v == null) return '—';
  return (v * 100).toFixed(1) + '%';
}

onMounted(async () => {
  await Promise.all([
    store.buscarCapacidade(),
    store.buscarPorEspecialidade(),
    store.buscarPorDiaTurno(),
  ]);
});
</script>
