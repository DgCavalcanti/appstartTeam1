<template>
  <div>
    <!-- ── Cabeçalho e filtros ──────────────────────────────────────────── -->
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-paper-text">Dashboard SAA</h1>
        <p class="text-sm text-gray-500">Distribuição de salas ambulatoriais</p>
      </div>
      <div class="flex flex-wrap gap-3">
        <select v-model="filtros.dia" class="form-control !py-1.5 !text-sm w-36">
          <option value="">Todos os dias</option>
          <option v-for="d in DIAS" :key="d">{{ d }}</option>
        </select>
        <select v-model="filtros.turno" class="form-control !py-1.5 !text-sm w-32">
          <option value="">Todos os turnos</option>
          <option v-for="t in TURNOS" :key="t">{{ t }}</option>
        </select>
        <select v-model="filtros.bloco" class="form-control !py-1.5 !text-sm w-32">
          <option value="">Todos os blocos</option>
          <option v-for="b in blocos" :key="b">{{ b }}</option>
        </select>
        <select v-model="filtros.status" class="form-control !py-1.5 !text-sm w-36">
          <option value="">Todos os status</option>
          <option v-for="s in STATUS_SALAS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </div>
    </div>

    <!-- ── Cards de indicadores ────────────────────────────────────────── -->
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
      <div class="bg-white rounded-lg shadow-paper p-4 text-center">
        <div class="text-3xl font-bold text-paper-primary">{{ store.indicadores.totalSalas }}</div>
        <div class="text-xs text-gray-500 mt-1">Total de Salas</div>
      </div>
      <div class="bg-white rounded-lg shadow-paper p-4 text-center">
        <div class="text-3xl font-bold text-paper-success">{{ store.indicadores.salasDisponiveis }}</div>
        <div class="text-xs text-gray-500 mt-1">Disponíveis</div>
      </div>
      <div class="bg-white rounded-lg shadow-paper p-4 text-center">
        <div class="text-3xl font-bold text-paper-danger">{{ store.indicadores.salasBloqueadas }}</div>
        <div class="text-xs text-gray-500 mt-1">Bloqueadas</div>
      </div>
      <div class="bg-white rounded-lg shadow-paper p-4 text-center">
        <div class="text-3xl font-bold text-paper-warning">{{ store.indicadores.salasReforma }}</div>
        <div class="text-xs text-gray-500 mt-1">Em Reforma/Manutenção</div>
      </div>
      <div class="bg-white rounded-lg shadow-paper p-4 text-center">
        <div class="text-3xl font-bold text-paper-info">{{ gradesNoFiltro.length }}</div>
        <div class="text-xs text-gray-500 mt-1">Grades no Filtro</div>
      </div>
      <div
        class="rounded-lg shadow-paper p-4 text-center"
        :class="store.indicadores.conflitosCriticos > 0 ? 'bg-red-50 border border-red-200' : 'bg-white'"
      >
        <div class="text-3xl font-bold" :class="store.indicadores.conflitosCriticos > 0 ? 'text-red-600' : 'text-gray-400'">
          {{ store.indicadores.conflitosCriticos }}
        </div>
        <div class="text-xs text-gray-500 mt-1">Conflitos Críticos</div>
      </div>
    </div>

    <!-- ── Alertas de conflitos críticos ────────────────────────────────── -->
    <div v-if="conflitosVisiveis.length > 0" class="mb-6">
      <Card>
        <template #header>
          <div class="flex items-center gap-2">
            <ExclamationTriangleIcon class="h-5 w-5 text-red-500" />
            <h2 class="font-semibold text-red-700">Conflitos Identificados ({{ conflitosVisiveis.length }})</h2>
          </div>
        </template>
        <div class="space-y-2">
          <div
            v-for="c in conflitosVisiveis"
            :key="c.id"
            class="flex items-start gap-3 p-3 rounded-lg text-sm"
            :class="c.gravidade === 'critico' ? 'bg-red-50 border border-red-200' : 'bg-yellow-50 border border-yellow-200'"
          >
            <span
              class="shrink-0 px-2 py-0.5 rounded text-xs font-bold uppercase"
              :class="c.gravidade === 'critico' ? 'bg-red-600 text-white' : 'bg-yellow-500 text-white'"
            >{{ c.gravidade }}</span>
            <span class="text-gray-700">{{ c.descricao }}</span>
          </div>
        </div>
      </Card>
    </div>

    <!-- ── Grid visual de salas ─────────────────────────────────────────── -->
    <Card class="mb-6">
      <template #header>
        <h2 class="font-semibold">Grade Visual de Salas</h2>
      </template>
      <div v-if="salasFiltradas.length === 0" class="text-center text-gray-400 py-8">
        Nenhuma sala encontrada. Importe os dados via CSV.
      </div>
      <div v-else class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-7 gap-3">
        <button
          v-for="sala in salasFiltradas"
          :key="sala.id"
          @click="abrirDetalhe(sala)"
          class="flex flex-col items-center justify-center p-3 rounded-lg border-2 text-xs font-medium transition-all hover:scale-105 cursor-pointer"
          :class="cardClassSala(sala)"
          :title="sala.especialidade_preferencial"
        >
          <span class="font-bold text-base">{{ sala.numero }}</span>
          <span class="text-center leading-tight mt-1">{{ sala.bloco }}</span>
          <span class="mt-1 px-1 rounded text-white text-[10px]" :class="badgeStatusSala(sala.status)">
            {{ STATUS_LABEL[sala.status] }}
          </span>
          <!-- indicador de conflito na sala -->
          <span v-if="store.getConflitosParaSala(sala.id).length > 0" class="mt-1 text-red-600">⚠</span>
        </button>
      </div>
      <!-- Legenda -->
      <div class="flex flex-wrap gap-4 mt-4 pt-4 border-t border-gray-100 text-xs text-gray-500">
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-green-100 border-2 border-green-400"></span> Disponível</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-red-100 border-2 border-red-400"></span> Bloqueada</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-yellow-100 border-2 border-yellow-400"></span> Reforma/Manutenção</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-blue-100 border-2 border-blue-400"></span> Ocupada</span>
        <span class="flex items-center gap-1">⚠ Com conflito</span>
      </div>
    </Card>

    <!-- ── Tabela de ocupação ────────────────────────────────────────────── -->
    <Card>
      <template #header>
        <h2 class="font-semibold">Tabela de Ocupação</h2>
      </template>
      <div v-if="gradesNoFiltro.length === 0" class="text-center text-gray-400 py-8">
        Nenhuma grade encontrada para os filtros aplicados.
      </div>
      <div v-else class="w-full overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-xs font-semibold text-gray-500 uppercase border-b border-gray-200 bg-gray-50">
            <tr>
              <th class="px-4 py-2 text-left">Especialidade</th>
              <th class="px-4 py-2 text-left">Profissional</th>
              <th class="px-4 py-2 text-left">Dia/Turno</th>
              <th class="px-4 py-2 text-left">Sala Alocada</th>
              <th class="px-4 py-2 text-left">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="grade in gradesNoFiltro" :key="grade.id" class="hover:bg-gray-50">
              <td class="px-4 py-3">{{ grade.especialidade }}</td>
              <td class="px-4 py-3 text-gray-500">{{ grade.profissional }}</td>
              <td class="px-4 py-3">{{ grade.dia_semana }} / {{ grade.turno }}</td>
              <td class="px-4 py-3">
                <span v-if="store.getAlocacaoPorGrade(grade.id)">
                  {{ store.getSala(store.getAlocacaoPorGrade(grade.id)!.sala_id)?.numero ?? '—' }}
                  (Bloco {{ store.getSala(store.getAlocacaoPorGrade(grade.id)!.sala_id)?.bloco ?? '?' }})
                </span>
                <span v-else class="text-red-500 font-semibold">Sem sala</span>
              </td>
              <td class="px-4 py-3">
                <span
                  v-if="store.getConflitosParaGrade(grade.id).length > 0"
                  class="px-2 py-0.5 rounded bg-red-100 text-red-700 text-xs font-medium"
                >{{ store.getConflitosParaGrade(grade.id).length }} conflito(s)</span>
                <span v-else class="px-2 py-0.5 rounded bg-green-100 text-green-700 text-xs font-medium">OK</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- ── Modal detalhe de sala ─────────────────────────────────────────── -->
    <Modal :show="!!salaSelecionada" @close="salaSelecionada = null">
      <template #header>Detalhe — Sala {{ salaSelecionada?.numero }}</template>
      <DetalhesSala v-if="salaSelecionada" :sala="salaSelecionada" @fechar="salaSelecionada = null" />
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ExclamationTriangleIcon } from '@heroicons/vue/24/outline';
import { useSaaStore, type Sala } from '../stores/saa';
import Card from '../components/Card.vue';
import Modal from '../components/Modal.vue';
import DetalhesSala from '../components/DetalhesSala.vue';

const store = useSaaStore();

// ── Filtros ───────────────────────────────────────────────────────────────
const DIAS   = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
const TURNOS = ['Manhã', 'Tarde', 'Noite'];
const STATUS_SALAS = [
  { value: 'disponivel',  label: 'Disponível' },
  { value: 'bloqueada',   label: 'Bloqueada' },
  { value: 'reforma',     label: 'Em Reforma' },
  { value: 'manutencao',  label: 'Em Manutenção' },
  { value: 'ocupada',     label: 'Ocupada' },
];
const STATUS_LABEL: Record<string, string> = {
  disponivel: 'Disp.',
  bloqueada:  'Bloq.',
  reforma:    'Reforma',
  manutencao: 'Manut.',
  ocupada:    'Ocup.',
};

const filtros = ref({ dia: '', turno: '', bloco: '', status: '' });

const blocos = computed(() => [...new Set(store.salas.map(s => s.bloco))].sort());

// Salas filtradas pelo painel
const salasFiltradas = computed(() => store.salas.filter(s => {
  if (filtros.value.bloco  && s.bloco  !== filtros.value.bloco)  return false;
  if (filtros.value.status && s.status !== filtros.value.status) return false;
  return true;
}));

// Grades filtradas por dia/turno
const gradesNoFiltro = computed(() => store.grades.filter(g => {
  if (filtros.value.dia   && g.dia_semana !== filtros.value.dia)   return false;
  if (filtros.value.turno && g.turno      !== filtros.value.turno) return false;
  return true;
}));

// Apenas conflitos relevantes para o filtro atual
const conflitosVisiveis = computed(() => {
  const salaIds = new Set(salasFiltradas.value.map(s => s.id));
  const gradeIds = new Set(gradesNoFiltro.value.map(g => g.id));
  return store.conflitos.filter(c =>
    (!c.sala_id  || salaIds.has(c.sala_id)) &&
    (!c.grade_id || gradeIds.has(c.grade_id))
  ).slice(0, 20); // limitar para não travar o DOM
});

// ── Estilo dos cards de sala ──────────────────────────────────────────────
function cardClassSala(sala: Sala) {
  const temConflito = store.getConflitosParaSala(sala.id).length > 0;
  if (temConflito) return 'bg-red-50 border-red-400 text-red-800';
  switch (sala.status) {
    case 'disponivel': return 'bg-green-50  border-green-400  text-green-800';
    case 'bloqueada':  return 'bg-red-50    border-red-300    text-red-700';
    case 'reforma':
    case 'manutencao': return 'bg-yellow-50 border-yellow-400 text-yellow-800';
    case 'ocupada':    return 'bg-blue-50   border-blue-400   text-blue-800';
    default:           return 'bg-gray-50   border-gray-300   text-gray-700';
  }
}

function badgeStatusSala(status: string) {
  switch (status) {
    case 'disponivel': return 'bg-green-500';
    case 'bloqueada':  return 'bg-red-600';
    case 'reforma':
    case 'manutencao': return 'bg-yellow-500';
    case 'ocupada':    return 'bg-blue-500';
    default:           return 'bg-gray-400';
  }
}

// ── Detalhe de sala ───────────────────────────────────────────────────────
const salaSelecionada = ref<Sala | null>(null);
function abrirDetalhe(sala: Sala) { salaSelecionada.value = sala; }
</script>
