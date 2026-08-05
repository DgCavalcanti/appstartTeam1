<template>
  <div class="space-y-6 animate-fade-in-up">
    <section class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
      <div class="flex items-start justify-between gap-4 mb-1">
        <h2 class="text-lg font-semibold text-paper-text">
          Histórico ({{ cenarios.length }})
        </h2>
        <router-link
          to="/saa/importacao"
          class="px-3 py-1.5 rounded bg-paper-primary text-white text-sm font-medium hover:bg-paper-primary-hover shrink-0"
        >Nova importação</router-link>
      </div>
      <p class="text-sm text-gray-500 mb-4">
        Cada alocação é independente. Clonar cria uma variação sem tocar na original.
      </p>

      <div v-if="carregando" class="text-gray-400 py-6 text-center">Carregando…</div>

      <div v-else-if="!cenarios.length" class="text-gray-400 py-10 text-center">
        Nenhum cenário ainda.
        <router-link to="/saa/importacao" class="text-paper-primary hover:underline">
          Importe uma grade
        </router-link>
        para começar.
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full text-sm border-collapse">
          <thead>
            <tr class="text-xs text-gray-500 border-b border-gray-200">
              <th class="text-left py-2 pr-3 font-medium">Cenário</th>
              <th class="text-left px-2 font-medium">Criado em</th>
              <th class="text-right px-2 font-medium">Clínicas</th>
              <th class="text-right px-2 font-medium">Pavimentos</th>
              <th class="text-left px-2 font-medium">Status</th>
              <th class="text-right pl-2 font-medium">Ações</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="c in cenarios"
              :key="c.id"
              class="border-b border-gray-100"
              :class="c.id === idAtual ? 'bg-paper-primary/5' : ''"
            >
              <td class="py-2 pr-3 text-paper-text">
                {{ c.nome }}
                <span
                  v-if="c.id === idAtual"
                  class="text-[10px] px-1.5 py-0.5 rounded-full bg-paper-primary/15 text-paper-primary font-medium ml-1"
                  title="Cenário concluído mais recente — é o que abre em 'Alocação atual'"
                >atual</span>
                <span v-if="c.origem_id" class="text-xs text-gray-400 ml-1">
                  (clone de #{{ c.origem_id }})
                </span>
              </td>
              <td class="px-2 text-gray-500 text-xs whitespace-nowrap">
                {{ formatarData(c.criado_em) }}
              </td>
              <td class="text-right px-2 tabular-nums">{{ c.unidades }}</td>
              <td class="text-right px-2 tabular-nums">{{ c.pavimentos }}</td>
              <td class="px-2 text-xs text-gray-500">{{ c.status }}</td>
              <td class="text-right pl-2 whitespace-nowrap">
                <router-link
                  :to="`/saa/cenarios/${c.id}`"
                  class="text-paper-primary hover:underline text-xs mr-3 font-medium"
                >Abrir</router-link>
                <router-link
                  :to="`/saa/cenarios/${c.id}/visualizacao`"
                  class="text-paper-primary hover:underline text-xs mr-3"
                >Painel</router-link>
                <button class="text-paper-info hover:underline text-xs mr-3" @click="clonarCenario(c)">
                  Clonar
                </button>
                <button class="text-paper-danger hover:underline text-xs" @click="excluirCenario(c)">
                  Excluir
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import api from '../services/api';

interface Cenario {
  id: number; nome: string; status: string; etapa_atual: number;
  criado_em: string | null; origem_id: number | null;
  unidades: number; pavimentos: number;
}

const cenarios = ref<Cenario[]>([]);
const carregando = ref(true);

/** O cenário concluído mais recente — o mesmo que "Alocação atual" na sidebar abre. */
const idAtual = computed(
  () => cenarios.value.find(c => c.status === 'concluida')?.id ?? null
);

async function carregarHistorico() {
  carregando.value = true;
  try {
    // A API já devolve do mais recente ao mais antigo.
    const { data } = await api.get<Cenario[]>('/api/cenarios');
    cenarios.value = data;
  } finally {
    carregando.value = false;
  }
}

async function clonarCenario(cenario: Cenario) {
  const form = new FormData();
  form.append('nome', `${cenario.nome} (cópia)`);
  await api.post(`/api/cenarios/${cenario.id}/clonar`, form);
  await carregarHistorico();
}

async function excluirCenario(cenario: Cenario) {
  await api.delete(`/api/cenarios/${cenario.id}`);
  await carregarHistorico();
}

function formatarData(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

onMounted(carregarHistorico);
</script>
