<template>
  <div class="space-y-6">

    <!-- ── 1. Envio do arquivo ─────────────────────────────────────────── -->
    <section class="bg-white rounded-lg shadow-paper p-6">
      <h2 class="text-lg font-semibold text-paper-text mb-1">Etapa 1 — Importação</h2>
      <p class="text-sm text-gray-500 mb-4">
        Envie a exportação de grades do AGHU (.csv ou .xlsx). As linhas brutas são
        tratadas em memória e não são gravadas.
      </p>

      <label
        class="block border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition"
        :class="arrastando ? 'border-paper-primary bg-paper-primary/5' : 'border-gray-300 hover:border-paper-primary'"
        @dragover.prevent="arrastando = true"
        @dragleave.prevent="arrastando = false"
        @drop.prevent="aoSoltar"
      >
        <input type="file" accept=".csv,.xlsx,.xls" class="hidden" @change="aoEscolher" />
        <ArrowUpTrayIcon class="h-8 w-8 mx-auto text-gray-400 mb-2" />
        <p class="text-sm text-paper-text font-medium">
          {{ arquivo ? arquivo.name : 'Clique ou arraste o arquivo aqui' }}
        </p>
        <p v-if="arquivo" class="text-xs text-gray-500 mt-1">
          {{ (arquivo.size / 1024).toFixed(0) }} KB
        </p>
      </label>

      <div v-if="erro" class="mt-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
        {{ erro }}
      </div>

      <div class="flex items-center gap-3 mt-4">
        <button
          class="px-4 py-2 rounded bg-paper-primary text-white text-sm font-medium hover:bg-paper-primary-hover disabled:bg-paper-disabled disabled:text-gray-500"
          :disabled="!arquivo || carregando"
          @click="processar"
        >
          {{ carregando ? 'Processando…' : 'Importar e alocar' }}
        </button>
        <span v-if="carregando" class="text-sm text-gray-500">
          rodando o pipeline e o motor…
        </span>
      </div>
    </section>

    <!-- ── 2. Relatório de redução ─────────────────────────────────────── -->
    <section v-if="dados" class="bg-white rounded-lg shadow-paper p-6">
      <h2 class="text-lg font-semibold text-paper-text mb-4">Redução dos dados</h2>

      <div class="space-y-2">
        <div v-for="e in funil" :key="e.rotulo" class="flex items-center gap-3">
          <span class="w-40 text-sm text-paper-text shrink-0">{{ e.rotulo }}</span>
          <div class="flex-1 bg-gray-100 rounded h-6 relative overflow-hidden">
            <div class="h-full rounded transition-all" :class="e.cor" :style="{ width: e.pct + '%' }" />
          </div>
          <span class="w-28 text-right text-sm tabular-nums shrink-0">
            <strong>{{ e.valor.toLocaleString('pt-BR') }}</strong>
            <span class="text-gray-400 ml-1">{{ e.pct.toFixed(0) }}%</span>
          </span>
        </div>
      </div>

      <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6">
        <div v-for="d in descartes" :key="d.rotulo" class="bg-gray-50 rounded p-3">
          <p class="text-xs text-gray-500">{{ d.rotulo }}</p>
          <p class="text-lg font-semibold text-paper-text tabular-nums">{{ d.valor }}</p>
        </div>
      </div>

      <p v-if="dados.relatorio.slots_em_revisao > 0" class="mt-4 text-sm text-paper-text bg-paper-warning/10 border border-paper-warning/30 rounded p-3">
        <strong>{{ dados.relatorio.slots_em_revisao }}</strong> slots marcados para revisão —
        profissionais que atendem em duas clínicas no mesmo turno. Contam nas duas,
        e a etapa 2 permitirá conferir.
      </p>
    </section>

    <!-- ── 3. Unidades que não participam ──────────────────────────────── -->
    <section v-if="dados" class="bg-white rounded-lg shadow-paper p-6">
      <div class="flex items-start justify-between gap-4 mb-1">
        <h2 class="text-lg font-semibold text-paper-text">
          Unidades ({{ dados.clinicas.length }} participando)
        </h2>
        <button class="text-sm text-paper-info hover:underline shrink-0" @click="marcarSemSufixo">
          marcar as sem “(AMBULATÓRIO)”
        </button>
      </div>
      <p class="text-sm text-gray-500 mb-4">
        Desmarque o que não ocupa consultório. Alterar aqui reexecuta o pipeline.
      </p>

      <div class="max-h-64 overflow-y-auto border border-gray-200 rounded divide-y divide-gray-100">
        <label
          v-for="u in todasUnidades"
          :key="u"
          class="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer text-sm"
        >
          <input type="checkbox" :value="u" v-model="participantes" class="rounded" />
          <span :class="participantes.includes(u) ? 'text-paper-text' : 'text-gray-400 line-through'">
            {{ u }}
          </span>
        </label>
      </div>

      <button
        class="mt-4 px-4 py-2 rounded bg-paper-default text-white text-sm font-medium hover:bg-paper-default-hover disabled:bg-paper-disabled"
        :disabled="carregando"
        @click="processar"
      >
        Reprocessar
      </button>
    </section>

    <!-- ── 4. Panorama de salas ────────────────────────────────────────── -->
    <section v-if="dados" class="bg-white rounded-lg shadow-paper p-6">
      <h2 class="text-lg font-semibold text-paper-text mb-1">
        Panorama de salas
        <span class="text-sm font-normal text-gray-500">
          — {{ capacidadeTotal }} estações por turno
        </span>
      </h2>
      <p class="text-sm text-gray-500 mb-4">
        Informe quantas salas de cada tipo há no pavimento. A capacidade é
        calculada — uma sala de 2 estações comporta dois atendimentos e vale 2.
      </p>

      <div class="overflow-x-auto">
        <table class="w-full text-sm border-collapse">
          <thead>
            <tr class="text-xs text-gray-500 border-b border-gray-200">
              <th class="text-left py-2 pr-3 font-medium">Pavimento</th>
              <th class="px-2 font-medium text-center">Padrão<br />1 est.</th>
              <th class="px-2 font-medium text-center">Padrão<br />2 est.</th>
              <th class="px-2 font-medium text-center">Espec.<br />1 est.</th>
              <th class="px-2 font-medium text-center">Espec.<br />2 est.</th>
              <th class="px-2 font-medium text-center">Fechadas</th>
              <th class="pl-3 font-medium text-right">Estações</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in pavimentos" :key="i" class="border-b border-gray-100">
              <td class="py-1.5 pr-3 text-paper-text whitespace-nowrap">{{ p.nome_completo }}</td>
              <td v-for="campo in CAMPOS_SALA" :key="campo" class="px-1 text-center">
                <input
                  type="number" min="0"
                  v-model.number="p[campo]"
                  class="w-14 px-1 py-1 border border-gray-300 rounded text-sm text-center tabular-nums"
                />
              </td>
              <td class="pl-3 text-right tabular-nums font-medium">{{ capacidadeDe(p) }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr class="text-sm">
              <td colspan="6" class="pt-2 text-right text-gray-500">Total</td>
              <td class="pt-2 pl-3 text-right tabular-nums font-semibold">{{ capacidadeTotal }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>

    <!-- ── 5. Resultado da alocação ────────────────────────────────────── -->
    <section v-if="dados?.alocacao" class="bg-white rounded-lg shadow-paper p-6">
      <h2 class="text-lg font-semibold text-paper-text mb-4">Resultado da alocação</h2>

      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div class="bg-paper-success/10 border border-paper-success/30 rounded p-3">
          <p class="text-xs text-gray-500">Grades alocadas</p>
          <p class="text-2xl font-semibold text-paper-text tabular-nums">
            {{ dados.alocacao.total_alocado.toLocaleString('pt-BR') }}
          </p>
        </div>
        <div
          class="rounded p-3 border"
          :class="dados.alocacao.total_nao_alocado > 0
            ? 'bg-paper-danger/10 border-paper-danger/30'
            : 'bg-gray-50 border-gray-200'"
        >
          <p class="text-xs text-gray-500">Não alocadas</p>
          <p class="text-2xl font-semibold text-paper-text tabular-nums">
            {{ dados.alocacao.total_nao_alocado }}
          </p>
        </div>
        <div class="bg-gray-50 border border-gray-200 rounded p-3">
          <p class="text-xs text-gray-500">Clínicas</p>
          <p class="text-2xl font-semibold text-paper-text tabular-nums">{{ dados.clinicas.length }}</p>
        </div>
        <div class="bg-gray-50 border border-gray-200 rounded p-3">
          <p class="text-xs text-gray-500">Pico de demanda</p>
          <p class="text-2xl font-semibold text-paper-text tabular-nums">{{ picoDemanda }}</p>
        </div>
      </div>

      <!-- Ocupação por pavimento -->
      <h3 class="text-sm font-semibold text-paper-text mb-2">Ocupação por pavimento</h3>
      <div class="overflow-x-auto mb-6">
        <table class="w-full text-sm border-collapse">
          <thead>
            <tr class="text-xs text-gray-500 border-b border-gray-200">
              <th class="text-left py-2 pr-3 font-medium">Pavimento</th>
              <th class="text-right px-2 font-medium">Cap.</th>
              <th class="text-right px-2 font-medium">Clín.</th>
              <th v-for="(t, i) in dados.turnos" :key="i" class="px-1 font-medium text-center w-10">
                {{ rotuloTurno(t) }}
              </th>
              <th class="text-right pl-2 font-medium">Pico</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in dados.alocacao.por_pavimento" :key="p.pavimento_id" class="border-b border-gray-100">
              <td class="py-2 pr-3 text-paper-text">{{ p.nome }}</td>
              <td class="text-right px-2 tabular-nums text-gray-500">{{ p.capacidade }}</td>
              <td class="text-right px-2 tabular-nums text-gray-500">{{ p.clinicas }}</td>
              <td
                v-for="(q, i) in p.ocupacao"
                :key="i"
                class="text-center px-1 tabular-nums text-xs"
                :class="corOcupacao(q, p.capacidade)"
              >{{ q }}</td>
              <td class="text-right pl-2 tabular-nums font-medium">{{ p.ocupacao_pico }}%</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Clínica → pavimento -->
      <h3 class="text-sm font-semibold text-paper-text mb-2">Clínica → pavimento</h3>
      <div class="overflow-x-auto max-h-96 overflow-y-auto">
        <table class="w-full text-sm border-collapse">
          <thead class="sticky top-0 bg-white">
            <tr class="text-xs text-gray-500 border-b border-gray-200">
              <th class="text-left py-2 pr-3 font-medium">Clínica</th>
              <th class="text-left px-2 font-medium">Pavimento</th>
              <th v-for="(t, i) in dados.turnos" :key="i" class="px-1 font-medium text-center w-10">
                {{ rotuloTurno(t) }}
              </th>
              <th class="text-right pl-2 font-medium">Total</th>
              <th class="text-right pl-2 font-medium">Sem sala</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in clinicasOrdenadas" :key="c.clinica_id" class="border-b border-gray-100">
              <td class="py-2 pr-3 text-paper-text truncate max-w-xs" :title="c.nome">{{ c.nome }}</td>
              <td class="px-2 text-gray-500 text-xs">{{ c.pavimento }}</td>
              <td
                v-for="(q, i) in c.alocado"
                :key="i"
                class="text-center px-1 tabular-nums text-xs"
                :class="q === 0 ? 'text-gray-300' : 'text-paper-text'"
              >{{ q || '·' }}</td>
              <td class="text-right pl-2 tabular-nums">{{ c.total_alocado }}</td>
              <td
                class="text-right pl-2 tabular-nums"
                :class="c.total_nao_alocado > 0 ? 'text-paper-danger font-semibold' : 'text-gray-300'"
              >{{ c.total_nao_alocado || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Gravar como cenário -->
      <div class="mt-6 pt-4 border-t border-gray-200">
        <label class="form-label">Salvar como cenário</label>
        <p class="text-sm text-gray-500 mb-2">
          O cenário guarda sua própria cópia dos insumos — reabri-lo mostra
          exatamente o que gerou este resultado.
        </p>
        <div class="flex gap-3">
          <input
            v-model="nomeCenario"
            placeholder="Ex.: Grade de julho — proposta 1"
            class="form-control flex-1"
            @keyup.enter="salvarCenario"
          />
          <button
            class="px-4 py-2 rounded bg-paper-success text-white text-sm font-medium hover:opacity-90 disabled:bg-paper-disabled disabled:text-gray-500 whitespace-nowrap"
            :disabled="!nomeCenario.trim() || salvando"
            @click="salvarCenario"
          >
            {{ salvando ? 'Salvando…' : 'Salvar cenário' }}
          </button>
        </div>
      </div>
    </section>

    <!-- ── 6. Histórico de cenários ────────────────────────────────────── -->
    <section v-if="cenarios.length" class="bg-white rounded-lg shadow-paper p-6">
      <h2 class="text-lg font-semibold text-paper-text mb-1">
        Histórico ({{ cenarios.length }})
      </h2>
      <p class="text-sm text-gray-500 mb-4">
        Cada alocação é independente. Clonar cria uma variação sem tocar na original.
      </p>

      <div class="overflow-x-auto">
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
            <tr v-for="c in cenarios" :key="c.id" class="border-b border-gray-100">
              <td class="py-2 pr-3 text-paper-text">
                {{ c.nome }}
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
                <button class="text-paper-info hover:underline text-xs mr-3" @click="clonarCenario(c)">
                  clonar
                </button>
                <button class="text-paper-danger hover:underline text-xs" @click="excluirCenario(c)">
                  excluir
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
import { ArrowUpTrayIcon } from '@heroicons/vue/24/outline';
import api from '../services/api';

interface Turno { dia: string; periodo: string }
interface Cenario {
  id: number; nome: string; status: string; etapa_atual: number;
  criado_em: string | null; origem_id: number | null;
  unidades: number; pavimentos: number;
}
interface Clinica { id: number; nome: string; demanda: number[]; total: number; pico: number }
interface ResultadoClinica {
  clinica_id: number; nome: string; pavimento: string;
  alocado: number[]; nao_alocado: number[];
  total_alocado: number; total_nao_alocado: number;
}
interface OcupacaoPavimento {
  pavimento_id: number; nome: string; capacidade: number;
  ocupacao: number[]; demanda: number[];
  ocupacao_media: number; ocupacao_pico: number; clinicas: number;
}
interface Relatorio {
  linhas_brutas: number; linhas_apos_filtros: number;
  total_slots: number; total_demandas: number;
  percentual_apos_filtros: number; percentual_slots: number; percentual_demandas: number;
  descartadas_por_situacao: number; descartadas_por_condicao: number;
  descartadas_por_unidade: number; descartadas_por_dia: number;
  descartadas_por_noite: number; slots_em_revisao: number;
}
interface Resposta {
  arquivo: string;
  turnos: Turno[];
  relatorio: Relatorio;
  clinicas: Clinica[];
  unidades_novas: string[];
  alocacao: {
    total_alocado: number; total_nao_alocado: number;
    por_clinica: ResultadoClinica[]; por_pavimento: OcupacaoPavimento[];
  } | null;
}

const arquivo = ref<File | null>(null);
const arrastando = ref(false);
const carregando = ref(false);
const salvando = ref(false);
const erro = ref('');
const dados = ref<Resposta | null>(null);

const nomeCenario = ref('');
const cenarios = ref<Cenario[]>([]);

interface PavimentoEditavel {
  bloco: string; nome: string; nome_completo: string;
  padrao_1est: number; padrao_2est: number;
  esp_1est: number; esp_2est: number; fechada: number;
  [campo: string]: string | number;
}

/** Os quatro tipos de sala que entram na capacidade, mais as fechadas. */
const CAMPOS_SALA = ['padrao_1est', 'padrao_2est', 'esp_1est', 'esp_2est', 'fechada'] as const;

const pavimentos = ref<PavimentoEditavel[]>([]);
/** Todas as unidades já vistas no arquivo, participando ou não. */
const todasUnidades = ref<string[]>([]);
/** Subconjunto marcado — o que não está aqui vai para a lista de exclusão. */
const participantes = ref<string[]>([]);

const ABREV_DIA: Record<string, string> = {
  segunda: 'Seg', terca: 'Ter', quarta: 'Qua', quinta: 'Qui', sexta: 'Sex',
};

function rotuloTurno(t: Turno): string {
  return `${ABREV_DIA[t.dia] ?? t.dia}${t.periodo === 'manha' ? 'M' : 'T'}`;
}

/**
 * Capacidade em estações — sempre derivada das contagens, nunca digitada,
 * para não divergir do que o gestor edita. Espelha a fórmula do backend.
 */
function capacidadeDe(p: PavimentoEditavel): number {
  return (
    Number(p.padrao_1est || 0) +
    2 * Number(p.padrao_2est || 0) +
    Number(p.esp_1est || 0) +
    2 * Number(p.esp_2est || 0)
  );
}

const capacidadeTotal = computed(() =>
  pavimentos.value.reduce((s, p) => s + capacidadeDe(p), 0)
);

const picoDemanda = computed(() => {
  if (!dados.value?.alocacao) return 0;
  return Math.max(
    0,
    ...dados.value.alocacao.por_pavimento.flatMap(p => p.demanda)
  );
});

const clinicasOrdenadas = computed(() => {
  if (!dados.value?.alocacao) return [];
  return [...dados.value.alocacao.por_clinica].sort(
    (a, b) => b.total_alocado + b.total_nao_alocado - (a.total_alocado + a.total_nao_alocado)
  );
});

const funil = computed(() => {
  const r = dados.value?.relatorio;
  if (!r) return [];
  return [
    { rotulo: 'Bruto do AGHU', valor: r.linhas_brutas, pct: 100, cor: 'bg-gray-400' },
    { rotulo: 'Após filtros', valor: r.linhas_apos_filtros, pct: r.percentual_apos_filtros, cor: 'bg-paper-info' },
    { rotulo: 'grade_slot', valor: r.total_slots, pct: r.percentual_slots, cor: 'bg-paper-primary' },
    { rotulo: 'grade_demanda', valor: r.total_demandas, pct: r.percentual_demandas, cor: 'bg-paper-success' },
  ];
});

const descartes = computed(() => {
  const r = dados.value?.relatorio;
  if (!r) return [];
  return [
    { rotulo: 'Situação inativa', valor: r.descartadas_por_situacao },
    { rotulo: 'Condição sem sala', valor: r.descartadas_por_condicao },
    { rotulo: 'Não participa', valor: r.descartadas_por_unidade },
    { rotulo: 'Sábado', valor: r.descartadas_por_dia },
    { rotulo: 'Turno Noite', valor: r.descartadas_por_noite },
  ];
});

function corOcupacao(q: number, capacidade: number): string {
  if (capacidade === 0 || q === 0) return 'text-gray-300';
  const uso = q / capacidade;
  if (uso >= 1) return 'bg-paper-danger/20 text-paper-text font-semibold';
  if (uso >= 0.8) return 'bg-paper-warning/20 text-paper-text';
  if (uso >= 0.5) return 'bg-paper-success/15 text-paper-text';
  return 'text-gray-500';
}

function aoEscolher(evento: Event) {
  const alvo = evento.target as HTMLInputElement;
  definirArquivo(alvo.files?.[0] ?? null);
}

function aoSoltar(evento: DragEvent) {
  arrastando.value = false;
  definirArquivo(evento.dataTransfer?.files?.[0] ?? null);
}

function definirArquivo(novo: File | null) {
  if (!novo) return;
  arquivo.value = novo;
  erro.value = '';
  // Trocar de arquivo invalida a seleção de unidades da importação anterior.
  dados.value = null;
  todasUnidades.value = [];
  participantes.value = [];
}

function marcarSemSufixo() {
  participantes.value = todasUnidades.value.filter(u => u.toUpperCase().includes('AMBULAT'));
}

async function carregarPadroes() {
  if (pavimentos.value.length) return;
  // A estrutura do prédio vem do catálogo global, que sobrevive entre cenários.
  const { data } = await api.get('/api/cenarios/padroes');
  pavimentos.value = data.pavimentos.map((p: any) => ({ ...p }));
}

async function carregarHistorico() {
  const { data } = await api.get<Cenario[]>('/api/cenarios');
  cenarios.value = data;
}

async function salvarCenario() {
  if (!arquivo.value || !nomeCenario.value.trim()) return;
  salvando.value = true;
  erro.value = '';

  try {
    const excluidas = todasUnidades.value.filter(u => !participantes.value.includes(u));

    const form = new FormData();
    form.append('arquivo', arquivo.value);
    form.append('nome', nomeCenario.value.trim());
    form.append('pavimentos', JSON.stringify(pavimentos.value));
    form.append('unidades_excluidas', JSON.stringify(excluidas));

    await api.post('/api/cenarios', form);
    nomeCenario.value = '';
    await carregarHistorico();
  } catch (e: any) {
    erro.value = e?.response?.data?.detail ?? e?.message ?? 'Falha ao salvar o cenário';
  } finally {
    salvando.value = false;
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

async function processar() {
  if (!arquivo.value) return;
  carregando.value = true;
  erro.value = '';

  try {
    await carregarPadroes();

    const excluidas = todasUnidades.value.filter(u => !participantes.value.includes(u));

    const form = new FormData();
    form.append('arquivo', arquivo.value);
    form.append('pavimentos', JSON.stringify(pavimentos.value));
    form.append('unidades_excluidas', JSON.stringify(excluidas));

    const { data } = await api.post<Resposta>('/api/importacao', form);
    dados.value = data;

    // Na primeira passada, o arquivo define o universo de unidades e todas
    // entram participando. Nas seguintes, a seleção do gestor é preservada.
    if (!todasUnidades.value.length) {
      todasUnidades.value = data.clinicas.map(c => c.nome).sort();
      participantes.value = [...todasUnidades.value];
    }
  } catch (e: any) {
    erro.value = e?.response?.data?.detail ?? e?.message ?? 'Falha ao processar o arquivo';
  } finally {
    carregando.value = false;
  }
}
</script>
