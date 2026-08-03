<template>
  <div v-if="erroFatal" class="bg-white rounded-lg border border-paper-line shadow-paper p-6">
    <p class="text-paper-danger">{{ erroFatal }}</p>
    <router-link to="/saa/importacao" class="text-paper-info hover:underline text-sm">
      voltar ao histórico
    </router-link>
  </div>

  <div v-else-if="cenario" class="space-y-6 animate-fade-in-up">
    <!-- Cabeçalho -->
    <section class="bg-white rounded-lg border border-paper-line shadow-paper p-6 flex flex-wrap items-start justify-between gap-4 transition-shadow duration-300 hover:shadow-md">
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
        >Visualização</router-link>
        <router-link to="/saa/importacao" class="text-sm text-paper-info hover:underline">
          Histórico
        </router-link>
      </div>
    </section>

    <Stepper :etapas="etapas" @ir="irPara" />

    <div v-if="erro" class="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
      {{ erro }}
    </div>

    <!-- ── Etapa 1 ─────────────────────────────────────────────────────── -->
    <section v-if="etapaAtual === 1" class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
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
    <section v-else-if="etapaAtual === 2" class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
      <h3 class="text-lg font-semibold text-paper-text mb-1">Validar e ajustar grades</h3>
      <p class="text-sm text-gray-500 mb-4">
        Nº de grades por unidade em cada dia/turno. O ajuste é soberano: pode
        passar do que veio do AGHU. Dá para colar do Excel.
      </p>

      <div class="flex flex-wrap items-center gap-3 mb-3">
        <div class="relative">
          <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            v-model="buscaGrades"
            type="search"
            placeholder="Buscar clínica…"
            class="pl-8 pr-3 py-1.5 text-sm border border-gray-300 rounded w-52 focus:outline-none focus:border-paper-accent focus:ring-1 focus:ring-paper-accent/30 transition-all duration-200"
          />
        </div>
        <label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input type="checkbox" v-model="apenasAtivas" class="rounded" />
          apenas grades ativas
        </label>
        <button
          v-if="buscaGrades || apenasAtivas"
          class="text-xs text-paper-info hover:underline"
          @click="buscaGrades = ''; apenasAtivas = false"
        >limpar</button>
        <span class="text-xs text-gray-500 ml-auto tabular-nums bg-gray-100 px-2 py-0.5 rounded-full">
          Mostrando {{ linhasGradesFiltradas.length }} de {{ linhasGrades.length }}
        </span>
      </div>

      <PlanilhaEditavel
        :colunas="colunasGrades"
        :linhas="linhasGradesFiltradas"
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
    <section v-else-if="etapaAtual === 3" class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
      <h3 class="text-lg font-semibold text-paper-text mb-1">Panorama de salas</h3>
      <p class="text-sm text-gray-500 mb-4">
        Quantas salas de cada tipo há em cada pavimento. A capacidade em estações
        é calculada — uma sala de 2 estações vale 2. Salas fechadas não contam.
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
            <template v-for="(p, i) in panorama" :key="p.id">
              <tr v-if="mudaDeAndar(i)" class="bg-gray-50">
                <td colspan="7" class="py-1 pr-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Pavimento {{ p.andar || '—' }}
                </td>
              </tr>
              <tr class="border-b border-gray-100">
                <td class="py-1.5 pr-3 text-paper-text whitespace-nowrap">{{ p.nome_completo }}</td>
                <td v-for="campo in CAMPOS_SALA" :key="campo" class="px-1 text-center">
                  <input
                    type="number" min="0"
                    :value="p[campo]"
                    class="w-14 px-1 py-1 border border-gray-300 rounded text-sm text-center tabular-nums"
                    @change="editarSala(p, campo, $event)"
                  />
                </td>
                <td class="pl-3 text-right tabular-nums font-medium">{{ p.capacidade }}</td>
              </tr>
            </template>
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

    <!-- ── Etapa 4 — restrições ────────────────────────────────────────── -->
    <section v-else-if="etapaAtual === 4" class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
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
              >{{ r.tipo === 'obrigatorio' ? 'Obrigatória' : 'Preferencial' }}</span>
            </td>
            <td class="text-right pl-2">
              <button class="text-paper-danger hover:underline text-xs" @click="removerRestricao(r)">
                Remover
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
    </section>

    <!-- ── Etapa 5 — executar ──────────────────────────────────────────── -->
    <section v-else-if="etapaAtual === 5" class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
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
          <div class="bg-paper-success/10 border border-paper-success/30 rounded-lg p-3 transition-all duration-200 hover:shadow-sm">
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
          <PlanilhaEditavel
            :colunas="colunasResultado"
            :linhas="filtradas"
            :rotulo-grupo="grupoPavimento"
          />
        </FiltroAlocacao>
      </div>
    </section>

    <!-- ── Etapa 6 — ajustes manuais (arrastar e soltar) ───────────────── -->
    <section v-else-if="etapaAtual === 6" class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
      <h3 class="text-lg font-semibold text-paper-text mb-1">Ajustes manuais</h3>
      <p class="text-sm text-gray-500 mb-4">
        Arraste uma clínica de um pavimento para outro para realocá-la. Qualquer
        mudança é aceita — o sistema apenas avisa quando gera conflito. Para
        trocar duas, arraste uma e depois a outra.
      </p>

      <p v-if="!temResultado" class="text-gray-400 py-6 text-center">
        Execute a alocação na etapa 5 antes de ajustar.
      </p>

      <template v-else>
        <!-- Painel de conflitos -->
        <div
          v-if="conflitos.sobrecarga.length || conflitos.obrigatoriedade.length || conflitos.preferencia.length"
          class="mb-5 space-y-2"
        >
          <div
            v-if="conflitos.sobrecarga.length"
            class="bg-paper-danger/10 border border-paper-danger/30 rounded p-3"
          >
            <p class="text-sm font-medium text-paper-danger mb-1">
              Pavimentos sobrecarregados ({{ conflitos.sobrecarga.length }})
            </p>
            <ul class="text-xs text-paper-text space-y-0.5">
              <li v-for="(c, i) in conflitos.sobrecarga" :key="i">
                <strong>{{ c.pavimento }}</strong> — excede em {{ c.excesso }} estação(ões) na {{ c.turno }}
              </li>
            </ul>
          </div>

          <div
            v-if="conflitos.obrigatoriedade.length || conflitos.preferencia.length"
            class="bg-paper-warning/10 border border-paper-warning/30 rounded p-3"
          >
            <p class="text-sm font-medium text-paper-text mb-1">Regras não atendidas</p>
            <ul class="text-xs text-paper-text space-y-0.5">
              <li v-for="(c, i) in conflitos.obrigatoriedade" :key="'o' + i">
                <span class="text-paper-danger font-medium">Obrigatoriedade:</span>
                {{ c.unidade }} deveria estar em {{ c.alvo }} — está em {{ c.atual }}
              </li>
              <li v-for="(c, i) in conflitos.preferencia" :key="'p' + i" class="text-gray-500">
                <span class="font-medium">Preferência:</span>
                {{ c.unidade }} não está no pavimento preferido ({{ c.alvo }})
              </li>
            </ul>
          </div>
        </div>

        <!-- Quadro de pavimentos: arraste as clínicas entre os cards -->
        <div class="space-y-5">
          <div v-for="grupo in quadroPorAndar" :key="grupo.andar">
            <h4 class="text-sm font-semibold text-paper-text mb-2">{{ grupo.pavimento }}</h4>
            <div class="grid gap-3 md:grid-cols-2">
              <div
                v-for="b in grupo.blocos"
                :key="b.id"
                class="border rounded-lg p-3 transition-colors duration-150"
                :class="[
                  sobreId === b.id ? 'border-paper-primary bg-paper-primary/5' : 'border-gray-200',
                  sobrecarregado(b) ? 'ring-1 ring-paper-danger/30' : '',
                ]"
                @dragover.prevent="sobreId = b.id"
                @dragleave="aoSairDoCard(b.id)"
                @drop.prevent="soltarEm(b.id)"
              >
                <div class="flex items-center justify-between mb-2">
                  <p class="text-sm font-medium text-paper-text">{{ b.bloco }}</p>
                  <span
                    class="text-xs shrink-0"
                    :class="sobrecarregado(b) ? 'text-paper-danger font-medium' : 'text-gray-400'"
                  >{{ b.capacidade }} est.</span>
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <span
                    v-for="c in b.clinicas"
                    :key="c.id"
                    draggable="true"
                    class="text-xs px-2 py-1 rounded bg-gray-100 text-gray-700 cursor-grab active:cursor-grabbing hover:bg-gray-200 select-none"
                    :class="arrastandoId === c.id ? 'opacity-40' : ''"
                    :title="`${c.nome} · ${somaDemanda(c)} grades`"
                    @dragstart="arrastandoId = c.id"
                    @dragend="aoTerminarArraste"
                  >{{ c.nome }}</span>
                  <span v-if="!b.clinicas.length" class="text-xs text-gray-400 italic py-1">
                    solte uma clínica aqui
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
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
import { rotuloDia, rotuloPeriodo, rotuloTurno } from '../utils/turno';
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

/** Pavimentos do catálogo (com id), só para casar com o pavimento deste cenário. */
const catalogoPavimentos = ref<any[]>([]);

const clinicasAtivas = computed(
  () => (cenario.value?.unidades ?? []).filter((u: any) => u.participa).length
);
const etapaAtual = computed(() => cenario.value?.etapa_atual ?? 1);
const turnos = computed<{ dia: string; periodo: string }[]>(() => cenario.value?.turnos ?? []);

/** As 10 colunas de turno, comuns às etapas 2, 5 e 6. */
const colunasTurno = computed<Coluna[]>(() =>
  turnos.value.map((t, i) => ({
    chave: `t${i}`,
    rotulo: rotuloTurno(t),
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
  rascunho: 'Rascunho',
  em_andamento: 'Em andamento',
  concluida: 'Confirmado',
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

/** Remove acentos e baixa a caixa, para a busca casar "oftalmologia" etc. */
function normalizarTexto(texto: string): string {
  return texto.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

const buscaGrades = ref('');
const apenasAtivas = ref(false);

/** Filtra as linhas da etapa 2 por nome da clínica e/ou só as grades ativas. */
const linhasGradesFiltradas = computed(() => {
  const termo = normalizarTexto(buscaGrades.value);
  return linhasGrades.value.filter(linha => {
    if (apenasAtivas.value && !linha.participa) return false;
    if (termo && !normalizarTexto(linha.nome).includes(termo)) return false;
    return true;
  });
});

// ── Etapa 3 ────────────────────────────────────────────────────────────────

/** Os quatro tipos de sala que entram na capacidade, mais as fechadas. */
const CAMPOS_SALA = ['padrao_1est', 'padrao_2est', 'esp_1est', 'esp_2est', 'fechada'] as const;

/**
 * A lista já vem agrupada por andar (pavimento 1 e seus blocos, depois
 * pavimento 2 e os seus...); aqui só decidimos onde começa cada grupo,
 * comparando com o pavimento anterior — como na tela de Importação.
 */
function mudaDeAndar(indice: number): boolean {
  if (indice === 0) return true;
  return panorama.value[indice].andar !== panorama.value[indice - 1].andar;
}

/** Edição de uma contagem de salas no panorama, persistindo na hora. */
function editarSala(p: any, campo: string, evento: Event) {
  const alvo = evento.target as HTMLInputElement;
  const valor = Number(alvo.value);
  if (!Number.isFinite(valor) || valor < 0) {
    alvo.value = String(p[campo] ?? 0); // valor inválido: devolve ao que estava
    return;
  }
  if (valor === p[campo]) return;
  editarPanorama({ linha: p, chave: campo, valor });
}

// ── Etapas 5 e 6 ───────────────────────────────────────────────────────────

const colunasResultado = computed<Coluna[]>(() => [
  { chave: 'pavimento', rotulo: 'Pavimento', largura: '12rem' },
  { chave: 'bloco', rotulo: 'Bloco', largura: '8rem' },
  { chave: 'nome', rotulo: 'Clínica', largura: '18rem' },
  ...colunasTurno.value.map(c => ({ ...c, editavel: false })),
  { chave: 'total_alocado', rotulo: 'Total' },
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

/** Na etapa 5 a tabela é lida "por pavimento": ordena por pavimento, bloco e nome. */
const linhasResultado = computed(() =>
  [...paraLinhas(cenario.value?.unidades ?? [])].sort(
    (a, b) =>
      (a.pavimento ?? '').localeCompare(b.pavimento ?? '', 'pt-BR') ||
      (a.bloco ?? '').localeCompare(b.bloco ?? '', 'pt-BR') ||
      a.nome.localeCompare(b.nome, 'pt-BR')
  )
);
/** Separa a tabela da etapa 5 por pavimento (linha de grupo). */
function grupoPavimento(linha: Record<string, any>): string {
  return linha.pavimento ?? '—';
}

// ── Etapa 6 — quadro de arrastar e soltar ────────────────────────────────────

/** Há resultado (motor rodou) assim que alguma clínica tem pavimento. */
const temResultado = computed(() =>
  (cenario.value?.unidades ?? []).some((u: any) => u.pavimento_id != null)
);

/** Soma da demanda semanal de uma clínica — o "tamanho" do chip. */
function somaDemanda(c: any): number {
  return (c.demanda ?? []).reduce((s: number, q: number) => s + q, 0);
}

/**
 * Quadro da etapa 6: os pavimentos do cenário agrupados por andar, cada um com
 * as clínicas participantes ali alocadas (ordenadas por nome).
 */
const quadroPorAndar = computed(() => {
  const porPavimento = new Map<number, any[]>();
  for (const u of cenario.value?.unidades ?? []) {
    if (!u.participa || u.pavimento_id == null) continue;
    if (!porPavimento.has(u.pavimento_id)) porPavimento.set(u.pavimento_id, []);
    porPavimento.get(u.pavimento_id)!.push(u);
  }
  const grupos = new Map<number, { andar: number; pavimento: string; blocos: any[] }>();
  for (const p of cenario.value?.pavimentos ?? []) {
    const clinicas = [...(porPavimento.get(p.id) ?? [])].sort((a, b) =>
      a.nome.localeCompare(b.nome, 'pt-BR')
    );
    if (!grupos.has(p.andar)) {
      grupos.set(p.andar, { andar: p.andar, pavimento: p.nome, blocos: [] });
    }
    grupos.get(p.andar)!.blocos.push({ ...p, clinicas });
  }
  return [...grupos.values()].sort((a, b) => a.andar - b.andar);
});

/** Um bloco está sobrecarregado se a carga de algum turno passa da capacidade. */
function sobrecarregado(bloco: any): boolean {
  return turnos.value.some((_t, i) => {
    const carga = bloco.clinicas.reduce((s: number, c: any) => s + (c.demanda?.[i] ?? 0), 0);
    return carga > bloco.capacidade;
  });
}

/**
 * Conflitos atuais, recalculados a cada movimento. "Aceitar e só avisar": nada
 * bloqueia — só listamos. Sobrecarga (capacidade) fica separada das regras
 * (obrigatoriedade/preferência).
 */
const conflitos = computed(() => {
  const sobrecarga: { pavimento: string; turno: string; excesso: number }[] = [];
  for (const grupo of quadroPorAndar.value) {
    for (const b of grupo.blocos) {
      turnos.value.forEach((t, i) => {
        const carga = b.clinicas.reduce((s: number, c: any) => s + (c.demanda?.[i] ?? 0), 0);
        if (carga > b.capacidade) {
          sobrecarga.push({
            pavimento: b.nome_completo,
            turno: `${rotuloDia(t.dia)} ${rotuloPeriodo(t.periodo)}`,
            excesso: carga - b.capacidade,
          });
        }
      });
    }
  }

  const porUnidade = new Map(
    (cenario.value?.unidades ?? []).map((u: any) => [u.id, u])
  );
  const porPavimento = new Map(
    (cenario.value?.pavimentos ?? []).map((p: any) => [p.id, p])
  );
  const obrigatoriedade: { unidade: string; alvo: string; atual: string }[] = [];
  const preferencia: { unidade: string; alvo: string }[] = [];
  for (const r of restricoes.value) {
    const u: any = porUnidade.get(r.unidade_id);
    if (!u || u.pavimento_id === r.pavimento_id) continue;
    const alvo: any = porPavimento.get(r.pavimento_id);
    const nomeAlvo = alvo?.nome_completo ?? r.pavimento;
    if (r.tipo === 'obrigatorio') {
      obrigatoriedade.push({
        unidade: r.unidade,
        alvo: nomeAlvo,
        atual: u.pavimento_completo ?? '—',
      });
    } else {
      preferencia.push({ unidade: r.unidade, alvo: nomeAlvo });
    }
  }

  return { sobrecarga, obrigatoriedade, preferencia };
});

// Estado do arrasto.
const arrastandoId = ref<number | null>(null);
const sobreId = ref<number | null>(null);

function aoSairDoCard(pavimentoId: number) {
  if (sobreId.value === pavimentoId) sobreId.value = null;
}

function aoTerminarArraste() {
  arrastandoId.value = null;
  sobreId.value = null;
}

/** Soltou um chip num pavimento: move a clínica para lá (se mudou de fato). */
function soltarEm(pavimentoId: number) {
  const id = arrastandoId.value;
  arrastandoId.value = null;
  sobreId.value = null;
  if (id == null) return;
  const unidade = (cenario.value?.unidades ?? []).find((u: any) => u.id === id);
  if (!unidade || unidade.pavimento_id === pavimentoId) return;
  mover(id, pavimentoId);
}

// ── Carregamento ───────────────────────────────────────────────────────────

async function carregar() {
  try {
    const [c, e, g, p, r, cat] = await Promise.all([
      api.get(`/api/cenarios/${cenarioId.value}`),
      api.get(`/api/cenarios/${cenarioId.value}/etapas`),
      api.get(`/api/cenarios/${cenarioId.value}/grades`),
      api.get(`/api/cenarios/${cenarioId.value}/panorama`),
      api.get(`/api/cenarios/${cenarioId.value}/restricoes`),
      api.get('/api/cenarios/padroes'),
    ]);
    cenario.value = c.data;
    etapas.value = e.data.etapas;
    grades.value = g.data.unidades;
    totaisGrades.value = g.data.totais_por_turno;
    panorama.value = p.data.pavimentos;
    restricoes.value = r.data.restricoes;
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
        await api.post('/api/cenarios/regras-padrao', {
          unidade: unidade.nome,
          pavimento_catalogo_id: pavimentoCatalogoId,
          tipo: nova.value.tipo,
        });
      }
    }

    nova.value = { unidade_id: 0, pavimento_id: 0, tipo: nova.value.tipo, salvarComoPadrao: false };
    await recarregarCenario();
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

/** Move uma clínica para outro pavimento (etapa 6). Aceita e só avisa. */
async function mover(unidadeId: number, pavimentoId: number) {
  await comErro(async () => {
    const { data } = await api.put(`/api/cenarios/${cenarioId.value}/alocacao`, {
      unidade_id: unidadeId,
      pavimento_id: pavimentoId,
    });
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
