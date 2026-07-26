<template>
  <div v-if="erroFatal" class="bg-white rounded-lg shadow-paper p-6">
    <p class="text-paper-danger">{{ erroFatal }}</p>
    <router-link to="/saa/importacao" class="text-paper-info hover:underline text-sm">
      voltar ao histórico
    </router-link>
  </div>

  <div v-else-if="cenario" class="space-y-6">
    <!-- Cabeçalho -->
    <section class="bg-white rounded-lg shadow-paper p-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-lg font-semibold text-paper-text">{{ cenario.nome }}</h2>
        <p class="text-sm text-gray-500 mt-1">
          {{ clinicasAtivas }} clínicas ·
          {{ cenario.pavimentos.length }} pavimentos ·
          {{ capacidadeTotal }} estações por turno
          <span v-if="cenario.origem_id"> · clone de #{{ cenario.origem_id }}</span>
        </p>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-xs px-2 py-1 rounded font-medium" :class="corDoStatus">{{ rotuloDoStatus }}</span>
        <button
          v-if="cenario.status !== 'concluida'"
          class="px-3 py-1.5 rounded bg-paper-success text-white text-sm hover:opacity-90 disabled:bg-paper-disabled disabled:text-gray-500"
          :disabled="!podeConcluir"
          :title="podeConcluir ? '' : 'Execute a alocação antes de concluir'"
          @click="concluir"
        >Concluir</button>
        <router-link
          v-if="temVisualizacao"
          :to="`/saa/cenarios/${cenarioId}/visualizacao`"
          class="text-sm text-paper-primary hover:underline font-medium"
        >visualização</router-link>
        <router-link to="/saa/importacao" class="text-sm text-paper-info hover:underline">
          histórico
        </router-link>
      </div>
    </section>

    <Stepper :etapas="etapas" @ir="irPara" />

    <div v-if="erro" class="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
      {{ erro }}
    </div>

    <!-- ── Etapa 1 ─────────────────────────────────────────────────────── -->
    <section v-if="etapaAtual === 1" class="bg-white rounded-lg shadow-paper p-6">
      <h3 class="text-lg font-semibold text-paper-text mb-1">Importação</h3>
      <p class="text-sm text-gray-500">
        As grades deste cenário vieram do AGHU e já foram tratadas. Para importar
        outro arquivo, crie um novo cenário — assim o histórico continua fiel.
      </p>
      <router-link
        to="/saa/importacao"
        class="inline-block mt-4 px-4 py-2 rounded bg-paper-default text-white text-sm hover:bg-paper-default-hover"
      >Nova importação</router-link>
    </section>

    <!-- ── Etapa 2 — grades ────────────────────────────────────────────── -->
    <section v-else-if="etapaAtual === 2" class="bg-white rounded-lg shadow-paper p-6">
      <h3 class="text-lg font-semibold text-paper-text mb-1">Validar e ajustar grades</h3>
      <p class="text-sm text-gray-500 mb-4">
        Nº de grades por unidade em cada dia/turno. O ajuste é soberano: pode
        passar do que veio do AGHU. Dá para colar do Excel.
      </p>

      <PlanilhaEditavel
        :colunas="colunasGrades"
        :linhas="linhasGrades"
        :rodape="rodapeGrades"
        :cor-da-celula="realceGrade"
        @editar="editarGrade"
      >
        <template #celula-nome="{ linha }">
          <span :class="linha.participa ? '' : 'text-gray-400 line-through'">
            {{ linha.nome }}
          </span>
          <span
            v-if="linha.slots_em_revisao"
            class="ml-1 text-[10px] px-1 rounded bg-paper-warning/20 text-paper-text"
            :title="`${linha.slots_em_revisao} profissional(is) atendendo em duas clínicas no mesmo turno`"
          >revisar</span>
        </template>
        <template #celula-participa="{ linha }">
          <input
            type="checkbox"
            :checked="linha.participa"
            class="rounded"
            @change="alternarParticipacao(linha, $event)"
          />
        </template>
      </PlanilhaEditavel>
    </section>

    <!-- ── Etapa 3 — panorama de salas ─────────────────────────────────── -->
    <section v-else-if="etapaAtual === 3" class="bg-white rounded-lg shadow-paper p-6">
      <h3 class="text-lg font-semibold text-paper-text mb-1">Panorama de salas</h3>
      <p class="text-sm text-gray-500 mb-4">
        Quantas salas de cada tipo há em cada pavimento. A capacidade em estações
        é calculada — uma sala de 2 estações vale 2. Salas fechadas não contam.
      </p>

      <PlanilhaEditavel
        :colunas="colunasPanorama"
        :linhas="panorama"
        :rodape="rodapePanorama"
        @editar="editarPanorama"
      />
    </section>

    <!-- ── Etapa 4 — restrições ────────────────────────────────────────── -->
    <section v-else-if="etapaAtual === 4" class="bg-white rounded-lg shadow-paper p-6">
      <h3 class="text-lg font-semibold text-paper-text mb-1">Obrigatoriedades e preferências</h3>
      <p class="text-sm text-gray-500 mb-4">
        <strong>Obrigatória</strong> é uma trava: a clínica vai para aquele
        pavimento mesmo que isso deixe grades sem sala — é a única coisa capaz de
        gerar sobra. <strong>Preferencial</strong> é um puxão: cede quando o
        pavimento não comporta a clínica inteira.
      </p>

      <div class="flex flex-wrap items-end gap-3 mb-5">
        <div class="flex-1 min-w-[12rem]">
          <label class="form-label">Clínica</label>
          <select v-model.number="nova.unidade_id" class="form-control">
            <option :value="0">— selecione —</option>
            <option v-for="u in unidadesParticipantes" :key="u.id" :value="u.id">{{ u.nome }}</option>
          </select>
        </div>
        <div class="flex-1 min-w-[12rem]">
          <label class="form-label">Pavimento</label>
          <select v-model.number="nova.pavimento_id" class="form-control">
            <option :value="0">— selecione —</option>
            <option v-for="p in panorama" :key="p.id" :value="p.id">{{ p.nome_completo }}</option>
          </select>
        </div>
        <div class="min-w-[10rem]">
          <label class="form-label">Tipo</label>
          <select v-model="nova.tipo" class="form-control">
            <option value="obrigatorio">Obrigatória</option>
            <option value="preferencial">Preferencial</option>
          </select>
        </div>
        <button
          class="px-4 py-2 rounded bg-paper-primary text-white text-sm hover:bg-paper-primary-hover disabled:bg-paper-disabled disabled:text-gray-500"
          :disabled="!nova.unidade_id || !nova.pavimento_id"
          @click="adicionarRestricao"
        >Adicionar</button>
      </div>

      <label class="flex items-center gap-2 text-xs text-gray-500 mb-4 -mt-2">
        <input type="checkbox" v-model="nova.salvarComoPadrao" class="rounded" />
        salvar também como regra padrão do catálogo (vale para os próximos cenários novos)
      </label>

      <table class="w-full text-sm border-collapse">
        <thead>
          <tr class="text-xs text-gray-500 border-b border-gray-200">
            <th class="text-left py-2 pr-3 font-medium">Clínica</th>
            <th class="text-left px-2 font-medium">Pavimento</th>
            <th class="text-left px-2 font-medium">Tipo</th>
            <th class="text-right pl-2 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in restricoes" :key="r.id" class="border-b border-gray-100">
            <td class="py-2 pr-3 text-paper-text">{{ r.unidade }}</td>
            <td class="px-2 text-gray-600">{{ r.pavimento }}</td>
            <td class="px-2">
              <span
                class="text-xs px-2 py-0.5 rounded"
                :class="r.tipo === 'obrigatorio'
                  ? 'bg-paper-danger/15 text-paper-text'
                  : 'bg-paper-info/15 text-paper-text'"
              >{{ r.tipo === 'obrigatorio' ? 'obrigatória' : 'preferencial' }}</span>
            </td>
            <td class="text-right pl-2">
              <button class="text-paper-danger hover:underline text-xs" @click="removerRestricao(r)">
                remover
              </button>
            </td>
          </tr>
          <tr v-if="!restricoes.length">
            <td colspan="4" class="py-6 text-center text-gray-400">
              Nenhuma restrição. O motor vai distribuir livremente.
            </td>
          </tr>
        </tbody>
      </table>

      <div class="mt-6 pt-5 border-t border-gray-200">
        <h4 class="text-sm font-semibold text-paper-text mb-1">
          Regras padrão do catálogo
          <span class="text-xs font-normal text-gray-400">({{ regrasPadrao.length }})</span>
        </h4>
        <p class="text-xs text-gray-500 mb-4">
          Pré-configuração aplicada automaticamente — já ponderada no motor —
          a cada <strong>novo</strong> cenário criado a partir de agora. Editar
          ou remover aqui não afeta este cenário nem outros já criados; e
          alterações neste cenário (acima) não mudam o padrão global a menos
          que você marque "salvar também como regra padrão".
        </p>

        <div class="flex flex-wrap items-end gap-3 mb-4">
          <div class="flex-1 min-w-[12rem]">
            <label class="form-label">Clínica</label>
            <select v-model.number="novaRegraPadrao.unidade_id" class="form-control">
              <option :value="0">— selecione —</option>
              <option v-for="u in grades" :key="u.id" :value="u.id">{{ u.nome }}</option>
            </select>
          </div>
          <div class="flex-1 min-w-[12rem]">
            <label class="form-label">Pavimento</label>
            <select v-model.number="novaRegraPadrao.pavimento_catalogo_id" class="form-control">
              <option :value="0">— selecione —</option>
              <option v-for="p in catalogoPavimentos" :key="p.id" :value="p.id">{{ p.nome_completo }}</option>
            </select>
          </div>
          <div class="min-w-[10rem]">
            <label class="form-label">Tipo</label>
            <select v-model="novaRegraPadrao.tipo" class="form-control">
              <option value="obrigatorio">Obrigatória</option>
              <option value="preferencial">Preferencial</option>
            </select>
          </div>
          <button
            class="px-4 py-2 rounded bg-paper-default text-white text-sm hover:bg-paper-default-hover disabled:bg-paper-disabled disabled:text-gray-500"
            :disabled="!novaRegraPadrao.unidade_id || !novaRegraPadrao.pavimento_catalogo_id"
            @click="adicionarRegraPadraoAvulsa"
          >Adicionar regra padrão</button>
        </div>

        <table class="w-full text-xs border-collapse">
          <tbody>
            <tr v-for="r in regrasPadrao" :key="r.id" class="border-b border-gray-100">
              <td class="py-1.5 pr-3 text-paper-text">{{ r.unidade }}</td>
              <td class="px-2 text-gray-600">{{ r.pavimento }}</td>
              <td class="px-2">
                <span
                  class="px-1.5 py-0.5 rounded"
                  :class="r.tipo === 'obrigatorio' ? 'bg-paper-danger/15' : 'bg-paper-info/15'"
                >{{ r.tipo === 'obrigatorio' ? 'obrigatória' : 'preferencial' }}</span>
              </td>
              <td class="text-right pl-2">
                <button class="text-paper-danger hover:underline" @click="removerRegraPadrao(r)">remover</button>
              </td>
            </tr>
            <tr v-if="!regrasPadrao.length">
              <td colspan="4" class="py-4 text-center text-gray-400">Nenhuma regra padrão definida.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ── Etapa 5 — executar ──────────────────────────────────────────── -->
    <section v-else-if="etapaAtual === 5" class="bg-white rounded-lg shadow-paper p-6">
      <h3 class="text-lg font-semibold text-paper-text mb-1">Executar a alocação</h3>
      <p class="text-sm text-gray-500 mb-4">
        Cada clínica é alocada inteira num pavimento, para a semana toda. O que
        varia entre turnos é quantas salas ela usa.
      </p>

      <button
        class="px-4 py-2 rounded bg-paper-primary text-white text-sm font-medium hover:bg-paper-primary-hover disabled:bg-paper-disabled disabled:text-gray-500"
        :disabled="ocupado"
        @click="executar"
      >{{ ocupado ? 'Executando…' : 'Executar alocação' }}</button>

      <div v-if="cenario.total_alocado || cenario.total_nao_alocado" class="mt-6">
        <div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-5">
          <div class="bg-paper-success/10 border border-paper-success/30 rounded p-3">
            <p class="text-xs text-gray-500">Grades alocadas</p>
            <p class="text-2xl font-semibold tabular-nums">{{ cenario.total_alocado }}</p>
          </div>
          <div
            class="rounded p-3 border"
            :class="cenario.total_nao_alocado
              ? 'bg-paper-danger/10 border-paper-danger/30'
              : 'bg-gray-50 border-gray-200'"
          >
            <p class="text-xs text-gray-500">Sem sala</p>
            <p class="text-2xl font-semibold tabular-nums">{{ cenario.total_nao_alocado }}</p>
          </div>
          <div class="bg-gray-50 border border-gray-200 rounded p-3">
            <p class="text-xs text-gray-500">Ocupação de pico</p>
            <p class="text-2xl font-semibold tabular-nums">{{ ocupacaoDePico }}%</p>
          </div>
        </div>

        <FiltroAlocacao :linhas="linhasResultado" v-slot="{ filtradas }">
          <PlanilhaEditavel :colunas="colunasResultado" :linhas="filtradas" />
        </FiltroAlocacao>
      </div>
    </section>

    <!-- ── Etapa 6 — ajustes manuais ───────────────────────────────────── -->
    <section v-else-if="etapaAtual === 6" class="bg-white rounded-lg shadow-paper p-6">
      <h3 class="text-lg font-semibold text-paper-text mb-1">Ajustes manuais</h3>
      <p class="text-sm text-gray-500 mb-4">
        Edite quantas grades cada clínica atende em cada turno. A demanda é fixa —
        o que sobra vira "sem sala". O total do pavimento não pode passar da
        capacidade.
      </p>

      <p v-if="!linhasAjuste.length" class="text-gray-400 py-6 text-center">
        Execute a alocação na etapa 5 antes de ajustar.
      </p>
      <FiltroAlocacao v-else :linhas="linhasAjuste" v-slot="{ filtradas }">
        <PlanilhaEditavel
          :colunas="colunasAjuste"
          :linhas="filtradas"
          :cor-da-celula="realceAjuste"
          @editar="ajustar"
        />
      </FiltroAlocacao>
    </section>
  </div>

  <p v-else class="text-gray-500">Carregando…</p>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

import FiltroAlocacao from '../components/FiltroAlocacao.vue';
import PlanilhaEditavel, { type Alteracao, type Coluna } from '../components/PlanilhaEditavel.vue';
import Stepper, { type EtapaResumo } from '../components/Stepper.vue';
import api from '../services/api';

const route = useRoute();
const cenarioId = computed(() => Number(route.params.id));

const cenario = ref<any>(null);
const etapas = ref<EtapaResumo[]>([]);
const grades = ref<any[]>([]);
const totaisGrades = ref<number[]>([]);
const panorama = ref<any[]>([]);
const restricoes = ref<any[]>([]);

const erro = ref('');
const erroFatal = ref('');
const ocupado = ref(false);
const nova = ref({ unidade_id: 0, pavimento_id: 0, tipo: 'obrigatorio', salvarComoPadrao: false });

/** Formulário próprio da seção "regras padrão", independente da restrição do cenário. */
const novaRegraPadrao = ref({ unidade_id: 0, pavimento_catalogo_id: 0, tipo: 'obrigatorio' });

/** Regras padrão do catálogo — pré-configuração aplicada a cenários novos. */
const regrasPadrao = ref<any[]>([]);
/** Pavimentos do catálogo (com id), só para casar com o pavimento deste cenário. */
const catalogoPavimentos = ref<any[]>([]);

const ABREV: Record<string, string> = {
  segunda: 'Seg', terca: 'Ter', quarta: 'Qua', quinta: 'Qui', sexta: 'Sex',
};

const clinicasAtivas = computed(
  () => (cenario.value?.unidades ?? []).filter((u: any) => u.participa).length
);
const etapaAtual = computed(() => cenario.value?.etapa_atual ?? 1);
const turnos = computed<{ dia: string; periodo: string }[]>(() => cenario.value?.turnos ?? []);

/** As 10 colunas de turno, comuns às etapas 2, 5 e 6. */
const colunasTurno = computed<Coluna[]>(() =>
  turnos.value.map((t, i) => ({
    chave: `t${i}`,
    rotulo: `${ABREV[t.dia] ?? t.dia}${t.periodo === 'manha' ? 'M' : 'T'}`,
    editavel: true,
  }))
);

const capacidadeTotal = computed(() =>
  panorama.value.reduce((s, p) => s + (p.capacidade ?? 0), 0)
);

const podeConcluir = computed(() =>
  etapas.value.some(e => e.numero === 5 && e.status === 'preenchida')
);

/** O painel existe assim que o motor rodou — mesmo que já esteja desatualizado. */
const temVisualizacao = computed(() =>
  etapas.value.some(
    e => e.numero === 5 && (e.status === 'preenchida' || e.status === 'desatualizada')
  )
);

const unidadesParticipantes = computed(() => grades.value.filter(u => u.participa));

const ROTULO_STATUS: Record<string, string> = {
  rascunho: 'rascunho',
  em_andamento: 'em andamento',
  concluida: 'confirmado',
};
const rotuloDoStatus = computed(() => ROTULO_STATUS[cenario.value?.status] ?? cenario.value?.status);
const corDoStatus = computed(() => {
  switch (cenario.value?.status) {
    case 'concluida': return 'bg-paper-success/15 text-paper-success';
    case 'em_andamento': return 'bg-paper-warning/15 text-paper-text';
    default: return 'bg-gray-100 text-gray-600';
  }
});

const ocupacaoDePico = computed(() => {
  const total = cenario.value?.total_alocado ?? 0;
  if (!total || !capacidadeTotal.value) return 0;
  const picos = (cenario.value?.unidades ?? []).reduce((acc: number[], u: any) => {
    (u.alocado ?? []).forEach((q: number, i: number) => (acc[i] = (acc[i] ?? 0) + q));
    return acc;
  }, [] as number[]);
  return Math.round((100 * Math.max(0, ...picos)) / capacidadeTotal.value);
});

// ── Etapa 2 ────────────────────────────────────────────────────────────────

const colunasGrades = computed<Coluna[]>(() => [
  { chave: 'nome', rotulo: 'Clínica', largura: '18rem' },
  { chave: 'participa', rotulo: 'Ativa', largura: '4rem' },
  ...colunasTurno.value,
  { chave: 'total', rotulo: 'Total' },
]);

/**
 * A API devolve a demanda como vetor; a planilha lê uma chave por coluna.
 * Sem este achatamento as células ficariam em branco — o valor existe, mas em
 * `demanda[i]`, e a coluna procura por `t{i}`.
 */
const linhasGrades = computed(() =>
  grades.value.map(u => {
    const linha: Record<string, any> = { ...u };
    (u.demanda ?? []).forEach((q: number, i: number) => (linha[`t${i}`] = q));
    return linha;
  })
);

const rodapeGrades = computed(() => {
  const linha: Record<string, any> = { nome: 'Total por turno', participa: '' };
  totaisGrades.value.forEach((q, i) => (linha[`t${i}`] = q));
  linha.total = totaisGrades.value.reduce((s, q) => s + q, 0);
  return linha;
});

function realceGrade(linha: Record<string, any>): string {
  return linha.participa ? '' : 'opacity-40';
}

// ── Etapa 3 ────────────────────────────────────────────────────────────────

const colunasPanorama: Coluna[] = [
  // A lista já vem agrupada por andar (pavimento 1 e seus blocos, depois
  // pavimento 2 e os seus...) — a coluna só torna esse agrupamento visível.
  { chave: 'andar', rotulo: 'Andar', largura: '4rem' },
  { chave: 'nome_completo', rotulo: 'Pavimento', largura: '16rem' },
  { chave: 'padrao_1est', rotulo: 'Padrão 1 est.', editavel: true },
  { chave: 'padrao_2est', rotulo: 'Padrão 2 est.', editavel: true },
  { chave: 'esp_1est', rotulo: 'Espec. 1 est.', editavel: true },
  { chave: 'esp_2est', rotulo: 'Espec. 2 est.', editavel: true },
  { chave: 'fechada', rotulo: 'Fechadas', editavel: true },
  { chave: 'salas_abertas', rotulo: 'Salas' },
  { chave: 'capacidade', rotulo: 'Estações' },
];

const rodapePanorama = computed(() => ({
  nome_completo: 'Total',
  salas_abertas: panorama.value.reduce((s, p) => s + p.salas_abertas, 0),
  capacidade: capacidadeTotal.value,
}));

// ── Etapas 5 e 6 ───────────────────────────────────────────────────────────

const colunasResultado = computed<Coluna[]>(() => [
  { chave: 'nome', rotulo: 'Clínica', largura: '18rem' },
  { chave: 'pavimento', rotulo: 'Pavimento', largura: '12rem' },
  ...colunasTurno.value.map(c => ({ ...c, editavel: false })),
  { chave: 'total_alocado', rotulo: 'Total' },
  { chave: 'total_nao_alocado', rotulo: 'Sem sala' },
]);

const colunasAjuste = computed<Coluna[]>(() => [
  { chave: 'nome', rotulo: 'Clínica', largura: '18rem' },
  { chave: 'pavimento', rotulo: 'Pavimento', largura: '12rem' },
  ...colunasTurno.value,
  { chave: 'total_nao_alocado', rotulo: 'Sem sala' },
]);

/** Achata o vetor `alocado` em colunas t0..t9 para a planilha consumir. */
function paraLinhas(unidades: any[]): any[] {
  return unidades
    .filter(u => u.participa && u.pavimento)
    .map(u => {
      const linha: Record<string, any> = { ...u, id: u.nome };
      (u.alocado ?? []).forEach((q: number, i: number) => (linha[`t${i}`] = q));
      return linha;
    });
}

const linhasResultado = computed(() => paraLinhas(cenario.value?.unidades ?? []));
const linhasAjuste = computed(() => paraLinhas(cenario.value?.unidades ?? []));

function realceAjuste(linha: Record<string, any>, coluna: Coluna): string {
  const i = Number(coluna.chave.replace('t', ''));
  if (Number.isNaN(i)) return '';
  return (linha.nao_alocado?.[i] ?? 0) > 0 ? 'bg-paper-danger/10' : '';
}

// ── Carregamento ───────────────────────────────────────────────────────────

async function carregar() {
  try {
    const [c, e, g, p, r, rp, cat] = await Promise.all([
      api.get(`/api/cenarios/${cenarioId.value}`),
      api.get(`/api/cenarios/${cenarioId.value}/etapas`),
      api.get(`/api/cenarios/${cenarioId.value}/grades`),
      api.get(`/api/cenarios/${cenarioId.value}/panorama`),
      api.get(`/api/cenarios/${cenarioId.value}/restricoes`),
      api.get('/api/cenarios/regras-padrao'),
      api.get('/api/cenarios/padroes'),
    ]);
    cenario.value = c.data;
    etapas.value = e.data.etapas;
    grades.value = g.data.unidades;
    totaisGrades.value = g.data.totais_por_turno;
    panorama.value = p.data.pavimentos;
    restricoes.value = r.data.restricoes;
    regrasPadrao.value = rp.data.regras;
    catalogoPavimentos.value = cat.data.pavimentos;
  } catch (e: any) {
    erroFatal.value = e?.response?.data?.detail ?? 'Não foi possível abrir o cenário';
  }
}

/** Casa o pavimento deste cenário com o pavimento correspondente no catálogo
 *  global, pela dupla (bloco, nome) — os dois carregam ids diferentes. */
function pavimentoCatalogoIdPara(pavimentoId: number): number | null {
  const daqui = panorama.value.find(p => p.id === pavimentoId);
  if (!daqui) return null;
  const doCatalogo = catalogoPavimentos.value.find(
    p => p.bloco === daqui.bloco && p.nome === daqui.nome
  );
  return doCatalogo?.id ?? null;
}

/** Recarrega o cenário — o resultado e os selos mudam a cada operação. */
async function recarregarCenario() {
  const [c, e] = await Promise.all([
    api.get(`/api/cenarios/${cenarioId.value}`),
    api.get(`/api/cenarios/${cenarioId.value}/etapas`),
  ]);
  cenario.value = c.data;
  etapas.value = e.data.etapas;
}

async function comErro(acao: () => Promise<void>) {
  erro.value = '';
  ocupado.value = true;
  try {
    await acao();
  } catch (e: any) {
    erro.value = e?.response?.data?.detail ?? e?.message ?? 'Operação recusada';
    // O backend recusou: recarrega para a tela refletir o estado real.
    await carregar();
  } finally {
    ocupado.value = false;
  }
}

onMounted(carregar);
watch(cenarioId, carregar);

// ── Ações ──────────────────────────────────────────────────────────────────

async function irPara(numero: number) {
  await comErro(async () => {
    const { data } = await api.post(`/api/cenarios/${cenarioId.value}/etapas/${numero}`);
    etapas.value = data.etapas;
    cenario.value = { ...cenario.value, etapa_atual: data.etapa_atual };
  });
}

async function editarGrade({ linha, chave, valor }: Alteracao) {
  const indice = Number(chave.replace('t', ''));
  const turno = turnos.value[indice];
  await comErro(async () => {
    const { data } = await api.put(`/api/cenarios/${cenarioId.value}/grades`, {
      celulas: [
        { unidade_id: linha.id, dia: turno.dia, turno: turno.periodo, quantidade: valor },
      ],
    });
    grades.value = data.unidades;
    totaisGrades.value = data.totais_por_turno;
    etapas.value = data.etapas;
  });
}

async function alternarParticipacao(linha: any, evento: Event) {
  const participa = (evento.target as HTMLInputElement).checked;
  await comErro(async () => {
    const { data } = await api.put(`/api/cenarios/${cenarioId.value}/grades`, {
      celulas: [],
      participacao: { [linha.id]: participa },
    });
    grades.value = data.unidades;
    totaisGrades.value = data.totais_por_turno;
    etapas.value = data.etapas;
  });
}

async function editarPanorama({ linha, chave, valor }: Alteracao) {
  await comErro(async () => {
    const { data } = await api.put(`/api/cenarios/${cenarioId.value}/panorama`, [
      { pavimento_id: linha.id, contagens: { [chave]: valor } },
    ]);
    panorama.value = data.pavimentos;
    etapas.value = data.etapas;
  });
}

async function adicionarRestricao() {
  await comErro(async () => {
    const { data } = await api.post(`/api/cenarios/${cenarioId.value}/restricoes`, {
      unidade_id: nova.value.unidade_id,
      pavimento_id: nova.value.pavimento_id,
      tipo: nova.value.tipo,
    });
    restricoes.value = data.restricoes;

    if (nova.value.salvarComoPadrao) {
      const unidade = grades.value.find(u => u.id === nova.value.unidade_id);
      const pavimentoCatalogoId = pavimentoCatalogoIdPara(nova.value.pavimento_id);
      if (unidade && pavimentoCatalogoId) {
        const { data: regras } = await api.post('/api/cenarios/regras-padrao', {
          unidade: unidade.nome,
          pavimento_catalogo_id: pavimentoCatalogoId,
          tipo: nova.value.tipo,
        });
        regrasPadrao.value = regras.regras;
      }
    }

    nova.value = { unidade_id: 0, pavimento_id: 0, tipo: nova.value.tipo, salvarComoPadrao: false };
    await recarregarCenario();
  });
}

async function removerRegraPadrao(r: any) {
  await comErro(async () => {
    await api.delete(`/api/cenarios/regras-padrao/${r.id}`);
    regrasPadrao.value = regrasPadrao.value.filter(x => x.id !== r.id);
  });
}

/** Adiciona uma regra padrão diretamente, sem passar pela restrição do cenário. */
async function adicionarRegraPadraoAvulsa() {
  const unidade = grades.value.find(u => u.id === novaRegraPadrao.value.unidade_id);
  if (!unidade) return;

  await comErro(async () => {
    const { data } = await api.post('/api/cenarios/regras-padrao', {
      unidade: unidade.nome,
      pavimento_catalogo_id: novaRegraPadrao.value.pavimento_catalogo_id,
      tipo: novaRegraPadrao.value.tipo,
    });
    regrasPadrao.value = data.regras;
    novaRegraPadrao.value = {
      unidade_id: 0,
      pavimento_catalogo_id: 0,
      tipo: novaRegraPadrao.value.tipo,
    };
  });
}

async function removerRestricao(r: any) {
  await comErro(async () => {
    const { data } = await api.delete(
      `/api/cenarios/${cenarioId.value}/restricoes/${r.id}`
    );
    restricoes.value = data.restricoes;
    await recarregarCenario();
  });
}

async function executar() {
  await comErro(async () => {
    const { data } = await api.post(`/api/cenarios/${cenarioId.value}/alocar`);
    cenario.value = data;
    const { data: e } = await api.get(`/api/cenarios/${cenarioId.value}/etapas`);
    etapas.value = e.etapas;
  });
}

async function ajustar({ linha, chave, valor }: Alteracao) {
  const indice = Number(chave.replace('t', ''));
  const turno = turnos.value[indice];
  const unidade = grades.value.find(u => u.nome === linha.nome);
  if (!unidade) return;

  await comErro(async () => {
    const { data } = await api.put(`/api/cenarios/${cenarioId.value}/resultado`, [
      { unidade_id: unidade.id, dia: turno.dia, turno: turno.periodo, qtd_alocada: valor },
    ]);
    cenario.value = data;
    const { data: e } = await api.get(`/api/cenarios/${cenarioId.value}/etapas`);
    etapas.value = e.etapas;
  });
}

async function concluir() {
  await comErro(async () => {
    await api.post(`/api/cenarios/${cenarioId.value}/concluir`);
    await recarregarCenario();
  });
}
</script>
