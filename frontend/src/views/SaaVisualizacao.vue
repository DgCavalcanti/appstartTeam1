<template>
  <div v-if="erroFatal" class="bg-white rounded-lg shadow-paper p-6">
    <p class="text-paper-danger">{{ erroFatal }}</p>
    <router-link :to="`/saa/cenarios/${cenarioId}`" class="text-paper-info hover:underline text-sm">
      voltar ao cenário
    </router-link>
  </div>

  <div v-else-if="painel" class="space-y-6">
    <!-- Cabeçalho -->
    <section class="bg-white rounded-lg shadow-paper p-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-lg font-semibold text-paper-text">{{ painel.nome }}</h2>
        <p class="text-sm text-gray-500 mt-1">Painel consolidado · somente leitura</p>
      </div>
      <div class="flex items-center gap-3">
        <router-link
          :to="`/saa/cenarios/${cenarioId}`"
          class="text-sm text-paper-info hover:underline"
        >abrir cenário</router-link>
      </div>
    </section>

    <div
      v-if="painel.desatualizada"
      class="bg-paper-warning/10 border border-paper-warning/30 rounded p-3 text-sm text-paper-text"
    >
      Algo mudou depois que esta alocação foi feita — o painel mostra o último
      resultado, que pode não valer mais. Reexecute a etapa 5 para atualizar.
    </div>

    <!-- Indicadores -->
    <section class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="bg-white rounded-lg shadow-paper p-4">
        <p class="text-xs text-gray-500">Grades alocadas</p>
        <p class="text-2xl font-semibold tabular-nums text-paper-text">
          {{ painel.resumo.total_alocado.toLocaleString('pt-BR') }}
        </p>
        <p class="text-xs text-gray-400 mt-1">de {{ painel.resumo.total_demanda.toLocaleString('pt-BR') }}</p>
      </div>

      <div
        class="bg-white rounded-lg shadow-paper p-4"
        :class="painel.resumo.total_nao_alocado ? 'ring-1 ring-paper-danger/30' : ''"
      >
        <p class="text-xs text-gray-500">Sem sala</p>
        <p class="text-2xl font-semibold tabular-nums" :class="painel.resumo.total_nao_alocado ? 'text-paper-danger' : 'text-paper-text'">
          {{ painel.resumo.total_nao_alocado }}
        </p>
        <p class="text-xs text-gray-400 mt-1">{{ painel.resumo.clinicas_com_sobra }} clínica(s)</p>
      </div>

      <div class="bg-white rounded-lg shadow-paper p-4">
        <p class="text-xs text-gray-500">Salas no pico</p>
        <p class="text-2xl font-semibold tabular-nums text-paper-text">
          {{ painel.resumo.salas_no_pico }}<span class="text-base text-gray-400">/{{ painel.resumo.salas_totais }}</span>
        </p>
        <p class="text-xs text-gray-400 mt-1">
          {{ painel.resumo.pavimentos_usados }}/{{ painel.resumo.pavimentos_totais }} pavimentos
        </p>
      </div>

      <div class="bg-white rounded-lg shadow-paper p-4">
        <p class="text-xs text-gray-500">Ocupação média</p>
        <p class="text-2xl font-semibold tabular-nums text-paper-text">{{ painel.resumo.ocupacao_media_pct }}%</p>
        <MedidorOcupacao :pct="painel.resumo.ocupacao_media_pct" :mostrar-valor="false" class="mt-2" />
      </div>
    </section>

    <!-- Demanda por turno -->
    <section class="bg-white rounded-lg shadow-paper p-6">
      <h3 class="text-sm font-semibold text-paper-text uppercase tracking-wide mb-4">Ocupação por turno</h3>
      <div class="flex items-end gap-2">
        <div v-for="(t, i) in painel.por_turno" :key="i" class="flex-1 flex flex-col items-center gap-1">
          <div
            class="w-full flex flex-col justify-end items-center"
            :style="{ height: ALTURA_GRAFICO + 'px' }"
            :title="`${t.alocado} alocadas${t.nao_alocado ? ` · ${t.nao_alocado} sem sala` : ''}`"
          >
            <div v-if="t.nao_alocado" class="w-full max-w-[2.5rem] bg-paper-danger/40 rounded-t" :style="{ height: alturaBarra(t.nao_alocado) }" />
            <div class="w-full max-w-[2.5rem] bg-paper-primary" :class="t.nao_alocado ? '' : 'rounded-t'" :style="{ height: alturaBarra(t.alocado) }" />
          </div>
          <span class="text-[10px] text-gray-400 tabular-nums">{{ t.ocupacao_pct }}%</span>
          <span class="text-[10px] text-gray-500">{{ rotuloTurno(t) }}</span>
        </div>
      </div>
      <div class="flex gap-4 mt-3 text-xs text-gray-500">
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-sm bg-paper-primary inline-block"></span> alocadas</span>
        <span class="flex items-center gap-1"><span class="w-3 h-3 rounded-sm bg-paper-danger/40 inline-block"></span> sem sala</span>
      </div>
    </section>

    <!-- Ocupação por pavimento — visão principal: quais unidades funcionais
         estão em cada pavimento, com ocupação, capacidade, salas, demanda não
         alocada e alertas. -->
    <section class="bg-white rounded-lg shadow-paper p-6">
      <h3 class="text-sm font-semibold text-paper-text uppercase tracking-wide mb-1">Pavimentos</h3>
      <p class="text-xs text-gray-500 mb-4">
        Visão principal — quais unidades funcionais estão alocadas em cada
        pavimento, e onde há sobra ou risco.
      </p>
      <div class="space-y-3">
        <div
          v-for="p in painel.por_pavimento"
          :key="p.id"
          class="border rounded-lg p-4"
          :class="p.alertas.length ? 'border-paper-danger/30 bg-paper-danger/5' : 'border-gray-200'"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p class="text-sm font-medium text-paper-text">{{ p.nome }}</p>
              <p class="text-xs text-gray-500 mt-0.5">
                {{ p.salas_no_pico }}/{{ p.salas_abertas }} salas no pico ·
                {{ p.capacidade }} estações de capacidade ·
                {{ p.clinicas.length }} unidade(s) funcional(is)
              </p>
            </div>
            <div class="flex items-center gap-3 shrink-0">
              <MedidorOcupacao :pct="p.ocupacao_pico_pct" :mostrar-valor="false" class="w-32" />
              <span class="text-sm tabular-nums font-medium text-paper-text w-12 text-right">{{ p.ocupacao_pico_pct }}%</span>
            </div>
          </div>

          <p v-if="p.total_nao_alocado" class="text-xs text-paper-danger font-medium mt-2">
            {{ p.total_nao_alocado }} grade(s) sem sala neste pavimento
          </p>

          <div v-if="p.alertas.length" class="mt-2 space-y-1">
            <p
              v-for="(a, i) in p.alertas"
              :key="i"
              class="text-xs text-paper-danger bg-white/60 border border-paper-danger/20 rounded px-2 py-1"
            >⚠ {{ a.mensagem }}</p>
          </div>

          <div v-if="p.clinicas.length" class="mt-3 flex flex-wrap gap-1.5">
            <span
              v-for="nome in p.clinicas"
              :key="nome"
              class="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600"
            >{{ nome }}</span>
          </div>
          <p v-else class="text-xs text-gray-400 mt-2">nenhuma unidade alocada aqui</p>
        </div>
      </div>
    </section>

    <!-- Clínica → pavimento (visão secundária, ordem alfabética, com busca/filtro) -->
    <section class="bg-white rounded-lg shadow-paper p-6">
      <h3 class="text-sm font-semibold text-paper-text uppercase tracking-wide mb-1">Unidades funcionais</h3>
      <p class="text-xs text-gray-500 mb-3">Visão secundária, em ordem alfabética.</p>

      <FiltroAlocacao :linhas="clinicasEmOrdemAlfabetica" v-slot="{ filtradas }">
        <div class="overflow-x-auto max-h-[32rem] overflow-y-auto">
          <table class="w-full text-sm border-collapse">
            <thead class="sticky top-0 bg-white">
              <tr class="text-xs text-gray-500 border-b border-gray-200">
                <th class="text-left py-2 pr-3 font-medium">Clínica</th>
                <th class="text-left px-2 font-medium">Pavimento</th>
                <th class="text-left px-2 font-medium">Bloco</th>
                <th v-for="(t, i) in painel.turnos" :key="i" class="px-1 font-medium text-center w-10">{{ rotuloTurno(t) }}</th>
                <th class="text-right pl-2 font-medium">Total</th>
                <th class="text-right pl-2 font-medium">Sem sala</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in filtradas" :key="c.nome" class="border-b border-gray-100">
                <td class="py-2 pr-3 text-paper-text truncate max-w-xs" :title="c.nome">{{ c.nome }}</td>
                <td class="px-2 text-gray-600 text-xs">{{ c.pavimento ?? '—' }}</td>
                <td class="px-2 text-gray-500 text-xs">{{ c.bloco ?? '—' }}</td>
                <td v-for="(q, i) in c.alocado" :key="i" class="text-center px-1 tabular-nums text-xs" :class="q === 0 ? 'text-gray-300' : 'text-paper-text'">
                  {{ q || '·' }}
                </td>
                <td class="text-right pl-2 tabular-nums">{{ c.total_alocado }}</td>
                <td class="text-right pl-2 tabular-nums" :class="c.total_nao_alocado ? 'text-paper-danger font-semibold' : 'text-gray-300'">
                  {{ c.total_nao_alocado || '—' }}
                </td>
              </tr>
              <tr v-if="!filtradas.length">
                <td :colspan="painel.turnos.length + 5" class="py-6 text-center text-gray-400">
                  Nenhuma clínica corresponde ao filtro.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </FiltroAlocacao>
    </section>
  </div>

  <p v-else class="text-gray-500">Carregando…</p>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import FiltroAlocacao from '../components/FiltroAlocacao.vue';
import MedidorOcupacao from '../components/MedidorOcupacao.vue';
import api from '../services/api';

const route = useRoute();
const cenarioId = computed(() => Number(route.params.id));

const painel = ref<any>(null);
const erroFatal = ref('');

const ABREV: Record<string, string> = {
  segunda: 'Seg', terca: 'Ter', quarta: 'Qua', quinta: 'Qui', sexta: 'Sex',
};

function rotuloTurno(t: { dia: string; periodo: string }): string {
  return `${ABREV[t.dia] ?? t.dia}${t.periodo === 'manha' ? 'M' : 'T'}`;
}

/** Altura em pixels da área do gráfico de barras. */
const ALTURA_GRAFICO = 128;

/** Barras dimensionadas contra o pico de demanda entre todos os turnos. */
const picoDemanda = computed(() =>
  Math.max(1, ...(painel.value?.por_turno ?? []).map((t: any) => t.demanda))
);

/**
 * Visão secundária: mesma lista de `por_clinica`, mas em ordem alfabética.
 * A ordem que a API devolve (sobra primeiro) é a que importa para o resumo;
 * esta tela é só para o gestor localizar uma unidade pelo nome. `FiltroAlocacao`
 * ainda deixa buscar por nome ou filtrar por bloco/pavimento em cima dela.
 */
const clinicasEmOrdemAlfabetica = computed(() =>
  [...(painel.value?.por_clinica ?? [])].sort((a: any, b: any) =>
    a.nome.localeCompare(b.nome, 'pt-BR')
  )
);

/**
 * Altura da barra em pixels — não em porcentagem.
 *
 * O contêiner das barras é uma linha flex com `items-end`, então a altura de
 * cada coluna é indefinida e uma barra com `height: %` colapsaria. Pixels
 * contra uma área de altura fixa resolvem isso.
 */
function alturaBarra(valor: number): string {
  return `${Math.round((ALTURA_GRAFICO * valor) / picoDemanda.value)}px`;
}

async function carregar() {
  painel.value = null;
  erroFatal.value = '';
  try {
    const { data } = await api.get(`/api/cenarios/${cenarioId.value}/visualizacao`);
    painel.value = data;
  } catch (e: any) {
    erroFatal.value =
      e?.response?.status === 409
        ? 'Este cenário ainda não foi alocado. Execute a etapa 5 antes de visualizar.'
        : e?.response?.data?.detail ?? 'Não foi possível abrir o painel';
  }
}

onMounted(carregar);
watch(cenarioId, carregar);
</script>
