<template>
  <div v-if="erroFatal" class="bg-white rounded-lg border border-paper-line shadow-paper p-6">
    <p class="text-paper-danger">{{ erroFatal }}</p>
    <router-link :to="`/saa/cenarios/${cenarioId}`" class="text-paper-info hover:underline text-sm">
      voltar ao cenário
    </router-link>
  </div>

  <div v-else-if="painel" class="space-y-6 animate-fade-in-up">
    <!-- Cabeçalho -->
    <section class="bg-white rounded-lg border border-paper-line shadow-paper p-6 flex flex-wrap items-start justify-between gap-4 transition-shadow duration-300 hover:shadow-md">
      <div>
        <h2 class="text-lg font-semibold text-paper-text">{{ painel.nome }}</h2>
        <p class="text-sm text-gray-500 mt-1">Painel consolidado · somente leitura</p>
      </div>
      <div class="flex items-center gap-3">
        <router-link
          :to="`/saa/cenarios/${cenarioId}`"
          class="text-sm text-paper-info hover:underline"
        >Abrir cenário</router-link>
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
      <div class="bg-white rounded-lg border border-paper-line shadow-paper p-4 transition-all duration-200 hover:shadow-md">
        <p class="text-xs text-gray-500">Grades alocadas</p>
        <p class="text-2xl font-semibold tabular-nums text-paper-text">
          {{ painel.resumo.total_alocado.toLocaleString('pt-BR') }}
        </p>
        <p class="text-xs text-gray-400 mt-1">de {{ painel.resumo.total_demanda.toLocaleString('pt-BR') }}</p>
      </div>

      <div
        class="bg-white rounded-lg border border-paper-line shadow-paper p-4 transition-all duration-200 hover:shadow-md"
        :class="painel.resumo.total_nao_alocado ? 'ring-1 ring-paper-danger/30' : ''"
      >
        <p class="text-xs text-gray-500">Sem sala</p>
        <p class="text-2xl font-semibold tabular-nums" :class="painel.resumo.total_nao_alocado ? 'text-paper-danger' : 'text-paper-text'">
          {{ painel.resumo.total_nao_alocado }}
        </p>
        <p class="text-xs text-gray-400 mt-1">{{ painel.resumo.clinicas_com_sobra }} clínica(s)</p>
      </div>

      <div class="bg-white rounded-lg border border-paper-line shadow-paper p-4 transition-all duration-200 hover:shadow-md">
        <p class="text-xs text-gray-500">Salas no pico</p>
        <p class="text-2xl font-semibold tabular-nums text-paper-text">
          {{ painel.resumo.salas_no_pico }}<span class="text-base text-gray-400">/{{ painel.resumo.salas_totais }}</span>
        </p>
        <p class="text-xs text-gray-400 mt-1">
          {{ painel.resumo.pavimentos_usados }}/{{ painel.resumo.pavimentos_totais }} pavimentos
        </p>
      </div>

      <div class="bg-white rounded-lg border border-paper-line shadow-paper p-4 transition-all duration-200 hover:shadow-md">
        <p class="text-xs text-gray-500">Ocupação média</p>
        <p class="text-2xl font-semibold tabular-nums text-paper-text">{{ painel.resumo.ocupacao_media_pct }}%</p>
        <MedidorOcupacao :pct="painel.resumo.ocupacao_media_pct" :mostrar-valor="false" class="mt-2" />
      </div>
    </section>

    <!-- Ocupação por turno — gráfico agrupado por dia -->
    <section class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
      <h3 class="text-sm font-semibold text-paper-text uppercase tracking-wide mb-6">Ocupação por turno</h3>

      <div class="flex">
        <!-- Eixo Y -->
        <div class="flex flex-col justify-between pr-2 shrink-0" :style="{ height: ALTURA_GRAFICO + 'px' }">
          <span v-for="tick in eixoY" :key="tick" class="text-[10px] text-gray-400 tabular-nums leading-none text-right w-8">
            {{ tick }}%
          </span>
        </div>

        <!-- Área do gráfico -->
        <div class="flex-1 relative">
          <!-- Linhas de grade horizontais -->
          <div class="absolute inset-0 flex flex-col justify-between pointer-events-none" :style="{ height: ALTURA_GRAFICO + 'px' }">
            <div v-for="tick in eixoY" :key="'g-'+tick" class="border-b border-gray-100 w-full"></div>
          </div>

          <!-- Grupos de barras por dia -->
          <div class="relative flex">
            <div
              v-for="(grupo, gi) in turnosPorDia"
              :key="grupo.dia"
              class="flex-1 flex flex-col items-center"
              :class="gi > 0 ? 'border-l border-gray-100' : ''"
            >
              <!-- Barras Manhã + Tarde -->
              <div class="flex items-end justify-center gap-3 w-full px-2" :style="{ height: ALTURA_GRAFICO + 'px' }">
                <div
                  v-for="t in grupo.turnos"
                  :key="t.periodo"
                  class="flex flex-col items-center flex-1 max-w-[3rem]"
                >
                  <!-- Porcentagem acima da barra -->
                  <span class="text-[10px] text-gray-500 tabular-nums mb-1">{{ t.ocupacao_pct }}%</span>
                  <!-- Barra -->
                  <div class="w-full flex flex-col justify-end items-center" :style="{ height: (ALTURA_GRAFICO - 18) + 'px' }">
                    <div
                      v-if="t.nao_alocado"
                      class="w-full bg-paper-danger/40 rounded-t transition-all duration-500 ease-out"
                      :style="{ height: alturaBarraEixo(t.nao_alocado) }"
                    />
                    <div
                      class="w-full bg-paper-primary transition-all duration-500 ease-out"
                      :class="t.nao_alocado ? '' : 'rounded-t'"
                      :style="{ height: alturaBarraEixo(t.alocado) }"
                    />
                  </div>
                </div>
              </div>
              <!-- Rótulos de período -->
              <div class="flex justify-center gap-3 w-full px-2 mt-1.5">
                <span
                  v-for="t in grupo.turnos"
                  :key="'l-'+t.periodo"
                  class="flex-1 max-w-[3rem] text-center text-[10px] text-gray-500"
                >{{ t.periodo === 'manha' ? 'Manhã' : 'Tarde' }}</span>
              </div>
              <!-- Nome do dia -->
              <span class="text-[11px] text-gray-500 font-medium mt-0.5">{{ grupo.rotulo }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Legenda -->
      <div class="flex gap-4 mt-4 text-xs text-gray-500">
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-sm bg-paper-primary inline-block"></span> alocadas</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3 rounded-sm bg-paper-danger/40 inline-block"></span> sem sala</span>
      </div>
    </section>

    <!-- Ocupação por pavimento — tabela compacta, um pavimento por linha -->
    <section class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
      <h3 class="text-sm font-semibold text-paper-text uppercase tracking-wide mb-4">Ocupação por pavimento</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm border-collapse">
          <thead>
            <tr class="text-xs text-gray-500 border-b border-gray-200">
              <th class="text-left py-2 pr-3 font-medium">Pavimento</th>
              <th class="text-right px-2 font-medium">Cap.</th>
              <th class="text-right px-2 font-medium">Clín.</th>
              <th v-for="(t, i) in painel.turnos" :key="i" class="px-2 font-medium text-center whitespace-nowrap">
                <span class="block leading-tight">{{ rotuloDia(t.dia) }}</span>
                <span class="block leading-tight font-normal text-gray-400">{{ rotuloPeriodo(t.periodo) }}</span>
              </th>
              <th class="text-right pl-2 font-medium">Pico</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in painel.por_pavimento" :key="p.id" class="border-b border-gray-100">
              <td class="py-2 pr-3 text-paper-text">{{ p.nome }}</td>
              <td class="text-right px-2 tabular-nums text-gray-500">{{ p.capacidade }}</td>
              <td class="text-right px-2 tabular-nums text-gray-500">{{ p.clinicas.length }}</td>
              <td
                v-for="(q, i) in p.ocupacao"
                :key="i"
                class="text-center px-1 tabular-nums text-xs"
                :class="corOcupacao(q, p.capacidade)"
              >{{ q }}</td>
              <td class="text-right pl-2 tabular-nums font-medium">{{ p.ocupacao_pico_pct }}%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Alocação por pavimento → bloco → clínica: a visão espacial do prédio. -->
    <section class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
      <h3 class="text-sm font-semibold text-paper-text uppercase tracking-wide mb-1">Alocação por pavimento</h3>
      <p class="text-xs text-gray-500 mb-4">
        Toque num andar para abrir seus blocos e as clínicas alocadas em cada um.
        A faixa de 10 quadradinhos é a semana (Seg M … Sex T) de cada clínica.
      </p>

      <div class="space-y-2">
        <div
          v-for="grupo in porAndar"
          :key="grupo.andar"
          class="border border-gray-200 rounded-lg overflow-hidden"
        >
          <!-- Cabeçalho do andar — clique para abrir/fechar -->
          <button
            type="button"
            class="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
            :aria-expanded="aberto(grupo.andar)"
            @click="alternar(grupo.andar)"
          >
            <span class="flex items-center gap-2 min-w-0">
              <ChevronRightIcon
                class="h-4 w-4 text-gray-400 shrink-0 transition-transform duration-200"
                :class="aberto(grupo.andar) ? 'rotate-90' : ''"
              />
              <span class="text-sm font-semibold text-paper-text truncate">{{ grupo.pavimento }}</span>
            </span>
            <span class="flex items-center gap-3 shrink-0 text-xs text-gray-500">
              <span
                v-if="grupo.semSala"
                class="text-paper-danger bg-paper-danger/10 rounded px-2 py-0.5 font-medium"
              >{{ grupo.semSala }} sem sala</span>
              <span>{{ grupo.blocos.length }} bloco(s) · {{ grupo.clinicas }} clínica(s)</span>
            </span>
          </button>

          <!-- Blocos do andar (só quando aberto) -->
          <div v-if="aberto(grupo.andar)" class="px-4 pb-4 pt-1 border-t border-gray-100 grid gap-3 md:grid-cols-2">
            <div
              v-for="b in grupo.blocos"
              :key="b.id"
              class="border rounded-lg p-4 transition-all duration-200 hover:shadow-sm"
              :class="b.total_nao_alocado ? 'border-paper-danger/30 bg-paper-danger/5' : 'border-gray-200'"
            >
              <!-- Cabeçalho do bloco -->
              <div class="flex items-start justify-between gap-2">
                <div>
                  <p class="text-sm font-medium text-paper-text">{{ b.bloco }}</p>
                  <p class="text-xs text-gray-500 mt-0.5">
                    {{ b.salas_no_pico }}/{{ b.salas_abertas }} salas no pico · {{ b.capacidade }} estações
                  </p>
                </div>
                <span
                  class="text-sm tabular-nums font-medium shrink-0"
                  :class="b.total_nao_alocado ? 'text-paper-danger' : 'text-paper-text'"
                  :title="`ocupação de pico: ${b.ocupacao_pico_pct}% da capacidade`"
                >{{ b.ocupacao_pico_pct }}%</span>
              </div>

              <!-- Alerta de sobra -->
              <div
                v-if="b.total_nao_alocado"
                class="mt-2 inline-flex items-center gap-1.5 text-xs text-paper-danger bg-paper-danger/10 rounded px-2 py-1"
              >{{ b.total_nao_alocado }} grade(s) sem sala</div>

              <!-- Clínicas do bloco, cada uma com sua faixa de turnos -->
              <div v-if="b.clinicas.length" class="mt-3 space-y-1.5">
                <div
                  v-for="c in b.clinicas"
                  :key="c.nome"
                  class="flex items-center justify-between gap-3"
                >
                  <span class="text-xs text-paper-text truncate" :title="c.nome">
                    {{ c.nome }}
                    <span v-if="c.total_nao_alocado" class="text-paper-danger">· {{ c.total_nao_alocado }} s/ sala</span>
                  </span>
                  <span class="flex gap-0.5 shrink-0">
                    <span
                      v-for="(t, i) in painel.turnos"
                      :key="i"
                      class="w-3 h-3.5 rounded-sm"
                      :class="corTurno(c, i)"
                      :title="tituloTurno(t, c, i)"
                    ></span>
                  </span>
                </div>
              </div>
              <p v-else class="text-xs text-gray-400 mt-2">nenhuma clínica alocada aqui</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Legenda -->
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-6 text-xs text-gray-500">
        <span class="flex items-center gap-1.5"><span class="w-3 h-3.5 rounded-sm bg-gray-100"></span> vazio</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3.5 rounded-sm bg-paper-success/30"></span> com grade</span>
        <span class="flex items-center gap-1.5"><span class="w-3 h-3.5 rounded-sm bg-paper-danger/40"></span> sem sala</span>
        <span class="ml-auto">faixa = Seg M … Sex T</span>
      </div>
    </section>
  </div>

  <p v-else class="text-gray-500">Carregando…</p>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { ChevronRightIcon } from '@heroicons/vue/24/outline';

import MedidorOcupacao from '../components/MedidorOcupacao.vue';
import { rotuloDia, rotuloPeriodo } from '../utils/turno';
import api from '../services/api';

const route = useRoute();
const cenarioId = computed(() => Number(route.params.id));

const painel = ref<any>(null);
const erroFatal = ref('');

const NOME_DIA: Record<string, string> = {
  segunda: 'Segunda-feira',
  terca: 'Terça-feira',
  quarta: 'Quarta-feira',
  quinta: 'Quinta-feira',
  sexta: 'Sexta-feira',
};

const ORDEM_DIA = ['segunda', 'terca', 'quarta', 'quinta', 'sexta'];

/** Altura em pixels da área do gráfico de barras. */
const ALTURA_GRAFICO = 160;

/** Barras dimensionadas contra o pico de demanda entre todos os turnos. */
const picoDemanda = computed(() =>
  Math.max(1, ...(painel.value?.por_turno ?? []).map((t: any) => t.demanda))
);

/**
 * Pico de ocupação em percentual — usado para escalar o eixo Y.
 */
const picoOcupacaoPct = computed(() =>
  Math.max(1, ...(painel.value?.por_turno ?? []).map((t: any) => t.ocupacao_pct ?? 0))
);

/**
 * Ticks do eixo Y — de 0 até o máximo arredondado para cima, em passos
 * razoáveis. Invertidos para renderizar de cima para baixo.
 */
const eixoY = computed(() => {
  const max = picoOcupacaoPct.value;
  const step = max <= 5 ? 1 : max <= 20 ? 5 : max <= 50 ? 10 : 20;
  const top = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = top; v >= 0; v -= step) ticks.push(v);
  return ticks;
});

/**
 * Agrupa os turnos por dia da semana para o gráfico de barras.
 * Cada grupo tem `dia`, `rotulo` e `turnos` (manhã, tarde).
 */
const turnosPorDia = computed(() => {
  const turnos: any[] = painel.value?.por_turno ?? [];
  const mapa = new Map<string, any[]>();
  for (const t of turnos) {
    if (!mapa.has(t.dia)) mapa.set(t.dia, []);
    mapa.get(t.dia)!.push(t);
  }
  // Ordena manhã antes de tarde dentro de cada dia
  for (const arr of mapa.values()) {
    arr.sort((a: any, b: any) => (a.periodo === 'manha' ? -1 : 1) - (b.periodo === 'manha' ? -1 : 1));
  }
  return ORDEM_DIA
    .filter(d => mapa.has(d))
    .map(d => ({ dia: d, rotulo: NOME_DIA[d] ?? d, turnos: mapa.get(d)! }));
});

/**
 * Agrupa os blocos por andar — o eixo principal da tela. `por_pavimento` já vem
 * ordenado por andar/id no backend, então a ordem de inserção é preservada.
 */
const porAndar = computed(() => {
  const grupos = new Map<number, { andar: number; pavimento: string; blocos: any[] }>();
  for (const b of painel.value?.por_pavimento ?? []) {
    if (!grupos.has(b.andar)) {
      grupos.set(b.andar, { andar: b.andar, pavimento: b.pavimento, blocos: [] });
    }
    grupos.get(b.andar)!.blocos.push(b);
  }
  return [...grupos.values()]
    .map(g => ({
      ...g,
      clinicas: g.blocos.reduce((s, b) => s + b.clinicas.length, 0),
      semSala: g.blocos.reduce((s, b) => s + b.total_nao_alocado, 0),
    }))
    .sort((a, b) => a.andar - b.andar);
});

/** Cor da célula de ocupação por turno na tabela por pavimento. */
function corOcupacao(q: number, capacidade: number): string {
  if (capacidade === 0 || q === 0) return 'text-gray-300';
  const uso = q / capacidade;
  if (uso >= 1) return 'bg-paper-danger/20 text-paper-text font-semibold';
  if (uso >= 0.8) return 'bg-paper-warning/20 text-paper-text';
  if (uso >= 0.5) return 'bg-paper-success/15 text-paper-text';
  return 'text-gray-500';
}

/** Andares abertos no acordeão — todos começam fechados (a lista compacta). */
const abertos = reactive<Record<number, boolean>>({});
function alternar(andar: number) {
  abertos[andar] = !abertos[andar];
}
function aberto(andar: number): boolean {
  return abertos[andar] === true;
}

/**
 * Cor de um turno na faixa da clínica. Clínica não tem capacidade própria, então
 * a faixa mostra o que é significável: sem sala (vermelho), com grade (verde) ou
 * vazio (cinza) — o gradiente de ocupação fica no pico do bloco.
 */
function corTurno(c: any, i: number): string {
  if ((c.nao_alocado?.[i] ?? 0) > 0) return 'bg-paper-danger/40';
  if ((c.alocado?.[i] ?? 0) > 0) return 'bg-paper-success/30';
  return 'bg-gray-100';
}

function tituloTurno(t: { dia: string; periodo: string }, c: any, i: number): string {
  const quando = `${rotuloDia(t.dia)} ${rotuloPeriodo(t.periodo)}`;
  const alocada = c.alocado?.[i] ?? 0;
  const semSala = c.nao_alocado?.[i] ?? 0;
  if (semSala > 0) return `${quando}: ${alocada} alocada(s), ${semSala} sem sala`;
  if (alocada > 0) return `${quando}: ${alocada} grade(s)`;
  return `${quando}: sem demanda`;
}

/**
 * Altura da barra em pixels escalonada pelo eixo Y (porcentagem de ocupação),
 * para alinhar com os ticks do eixo. A área útil desconta o espaço do label.
 */
function alturaBarraEixo(valor: number): string {
  const maxTick = eixoY.value[0] ?? 1;
  const area = ALTURA_GRAFICO - 18; // desconta rótulo de % acima da barra
  const pct = (valor / picoDemanda.value) * picoOcupacaoPct.value;
  return `${Math.max(0, Math.round((area * pct) / maxTick))}px`;
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
