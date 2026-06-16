<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-paper-text">Consultas AGHU</h1>
      <p class="text-sm text-gray-500 mt-1">
        Consultas paginadas. Use os filtros para refinar os resultados.
        O sistema nunca carrega todas as linhas no navegador.
      </p>
    </div>

    <!-- Alerta de erro -->
    <div v-if="store.erro" class="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm flex gap-2">
      <ExclamationTriangleIcon class="h-4 w-4 shrink-0 mt-0.5" />
      {{ store.erro }}
    </div>

    <!-- Filtros -->
    <div class="bg-white rounded-lg border border-gray-200 p-4 mb-4">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <label class="block text-xs text-gray-500 mb-1">Especialidade</label>
          <input v-model="filtros.especialidade" type="text" placeholder="Ex: CARDIOLOGIA"
            class="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:border-paper-primary" />
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">Turno</label>
          <select v-model="filtros.turno" class="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:border-paper-primary">
            <option value="">Todos</option>
            <option>MANHÃ</option>
            <option>TARDE</option>
            <option>NOITE</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">Dia da Semana</label>
          <select v-model="filtros.dia_semana" class="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:border-paper-primary">
            <option value="">Todos</option>
            <option>SEGUNDA</option>
            <option>TERÇA</option>
            <option>QUARTA</option>
            <option>QUINTA</option>
            <option>SEXTA</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">Situação</label>
          <input v-model="filtros.situacao_consulta" type="text" placeholder="Ex: AGENDADO"
            class="w-full text-sm border border-gray-200 rounded px-2 py-1.5 focus:outline-none focus:border-paper-primary" />
        </div>
      </div>
      <div class="flex items-center gap-4 mt-3">
        <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
          <input type="checkbox" v-model="filtros.apenas_excedentes" class="rounded" />
          Apenas excedentes
        </label>
        <button @click="buscar" :disabled="store.carregando"
          class="ml-auto bg-paper-primary text-white text-sm px-4 py-1.5 rounded hover:bg-paper-primary/90 disabled:opacity-50 transition-colors">
          Buscar
        </button>
        <button @click="limpar"
          class="text-sm text-gray-500 px-3 py-1.5 rounded border border-gray-200 hover:bg-gray-50 transition-colors">
          Limpar
        </button>
      </div>
    </div>

    <!-- Carregando -->
    <div v-if="store.carregando" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-paper-primary"></div>
    </div>

    <!-- Tabela de resultados -->
    <div v-if="!store.carregando && store.consultas.length > 0" class="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <span class="text-sm text-gray-500">{{ store.consultas.length }} resultado(s) — página {{ pagina }}</span>
        <div class="flex gap-2">
          <button @click="anterior" :disabled="pagina <= 1"
            class="text-xs px-3 py-1 border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50">
            Anterior
          </button>
          <button @click="proximo" :disabled="store.consultas.length < limit"
            class="text-xs px-3 py-1 border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50">
            Próxima
          </button>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th class="px-3 py-2 text-left">ID Consulta</th>
              <th class="px-3 py-2 text-left">Especialidade</th>
              <th class="px-3 py-2 text-left">Profissional</th>
              <th class="px-3 py-2 text-left">Data/Hora</th>
              <th class="px-3 py-2 text-left">Turno</th>
              <th class="px-3 py-2 text-left">Situação</th>
              <th class="px-3 py-2 text-center">Excedente</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(c, i) in store.consultas"
              :key="c.consulta_id ?? i"
              class="border-t border-gray-50 hover:bg-gray-50 transition-colors"
            >
              <td class="px-3 py-2 font-mono text-xs text-gray-600">{{ c.consulta_id ?? '—' }}</td>
              <td class="px-3 py-2 text-gray-800">{{ c.especialidade ?? '—' }}</td>
              <td class="px-3 py-2 text-gray-600">{{ c.profissional ?? '—' }}</td>
              <td class="px-3 py-2 text-gray-600 text-xs">{{ formatarData(c.data_hora_consulta) }}</td>
              <td class="px-3 py-2 text-gray-600">{{ c.turno ?? '—' }}</td>
              <td class="px-3 py-2">
                <span :class="badgeSituacao(c.situacao_consulta)">
                  {{ c.situacao_consulta ?? '—' }}
                </span>
              </td>
              <td class="px-3 py-2 text-center">
                <span v-if="c.consulta_excedente" class="text-red-600 font-bold">S</span>
                <span v-else class="text-gray-400">N</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Sem resultados -->
    <div v-if="!store.carregando && store.consultas.length === 0 && buscou"
      class="text-center py-12 text-gray-400">
      <MagnifyingGlassIcon class="h-10 w-10 mx-auto mb-2" />
      <p>Nenhuma consulta encontrada com esses filtros.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { ExclamationTriangleIcon, MagnifyingGlassIcon } from '@heroicons/vue/24/outline';
import { useAghuStore } from '../stores/aghu';

const store = useAghuStore();

const limit = 100;
const pagina = ref(1);
const buscou = ref(false);

const filtros = reactive({
  especialidade: '',
  turno: '',
  dia_semana: '',
  situacao_consulta: '',
  apenas_excedentes: false,
});

// Busca automática ao entrar na página, para sempre refletir a importação
// mais recente (sem isso, a tabela só carregava com um clique manual em
// "Buscar" e podia ficar mostrando dados de uma importação anterior).
onMounted(() => {
  buscar();
});

async function buscar() {
  buscou.value = true;
  await store.buscarConsultas({
    ...Object.fromEntries(Object.entries(filtros).filter(([, v]) => v !== '' && v !== false)),
    limit,
    offset: (pagina.value - 1) * limit,
  });
}

function limpar() {
  Object.assign(filtros, { especialidade: '', turno: '', dia_semana: '', situacao_consulta: '', apenas_excedentes: false });
  pagina.value = 1;
  buscar();
}

async function anterior() {
  if (pagina.value > 1) {
    pagina.value--;
    await buscar();
  }
}

async function proximo() {
  pagina.value++;
  await buscar();
}

function formatarData(v: string | null | undefined): string {
  if (!v) return '—';
  try {
    return new Date(v).toLocaleString('pt-BR');
  } catch {
    return v;
  }
}

function badgeSituacao(s: string | null | undefined): string {
  if (!s) return 'text-gray-400 text-xs';
  const u = s.toUpperCase();
  if (['AGENDADO', 'AGENDADA', 'MARCADO', 'MARCADA'].some(x => u.includes(x))) {
    return 'text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700';
  }
  if (['LIVRE', 'DISPONIVEL'].some(x => u.includes(x))) {
    return 'text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700';
  }
  if (['BLOQUEADO', 'BLOQUEIO'].some(x => u.includes(x))) {
    return 'text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600';
  }
  return 'text-xs text-gray-500';
}
</script>
