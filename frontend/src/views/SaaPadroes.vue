<template>
  <div class="space-y-6">
    <section class="bg-white rounded-lg shadow-paper p-6">
      <h2 class="text-lg font-semibold text-paper-text mb-1">Padrões</h2>
      <p class="text-sm text-gray-500">
        Configurações de referência que todo cenário novo herda ao ser criado.
        Editar aqui vale só para cenários futuros — os já salvos ficam intactos.
        Dentro de um cenário, o gestor ainda ajusta tudo nas etapas 3 e 4.
      </p>
    </section>

    <div v-if="erro" class="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
      {{ erro }}
    </div>

    <!-- ── Panorama de salas padrão ────────────────────────────────────── -->
    <section class="bg-white rounded-lg shadow-paper p-6">
      <h3 class="text-lg font-semibold text-paper-text mb-1">
        Panorama de salas
        <span class="text-sm font-normal text-gray-500">— {{ capacidadeTotal }} estações por turno</span>
      </h3>
      <p class="text-sm text-gray-500 mb-4">
        Quantas salas de cada tipo há em cada pavimento do HC. A capacidade em
        estações é calculada — uma sala de 2 estações vale 2.
      </p>

      <PlanilhaEditavel
        v-if="pavimentos.length"
        :colunas="colunasPanorama"
        :linhas="pavimentos"
        :rodape="rodapePanorama"
        @editar="editarPanorama"
      />
    </section>

    <!-- ── Restrições padrão ───────────────────────────────────────────── -->
    <section class="bg-white rounded-lg shadow-paper p-6">
      <h3 class="text-lg font-semibold text-paper-text mb-1">Obrigatoriedades e preferências padrão</h3>
      <p class="text-sm text-gray-500 mb-4">
        <strong>Obrigatória</strong> trava a clínica num pavimento;
        <strong>preferencial</strong> é um puxão que cede se não couber. Só as
        clínicas que participam de um cenário herdam a restrição na prática.
      </p>

      <div class="flex flex-wrap items-end gap-3 mb-5">
        <div class="flex-1 min-w-[14rem]">
          <label class="form-label">Clínica</label>
          <select v-model="nova.unidade_nome" class="form-control">
            <option value="">— selecione —</option>
            <option v-for="u in unidades" :key="u.nome" :value="u.nome">
              {{ u.nome }}{{ u.participa_default ? '' : ' (não participa por padrão)' }}
            </option>
          </select>
        </div>
        <div class="flex-1 min-w-[14rem]">
          <label class="form-label">Pavimento</label>
          <select v-model.number="nova.pavimento_catalogo_id" class="form-control">
            <option :value="0">— selecione —</option>
            <option v-for="p in pavimentosDestino" :key="p.id" :value="p.id">{{ p.nome_completo }}</option>
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
          :disabled="!nova.unidade_nome || !nova.pavimento_catalogo_id"
          @click="adicionarRestricao"
        >Adicionar</button>
      </div>

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
              Nenhuma restrição padrão. Cenários novos começam sem obrigatoriedades.
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import PlanilhaEditavel, { type Alteracao, type Coluna } from '../components/PlanilhaEditavel.vue';
import api from '../services/api';

interface Pavimento {
  id: number; bloco: string; nome: string; nome_completo: string;
  padrao_1est: number; padrao_2est: number; esp_1est: number; esp_2est: number;
  fechada: number; capacidade: number;
  [chave: string]: string | number;
}
interface Unidade { nome: string; participa_default: boolean }
interface PavimentoDestino { id: number; nome_completo: string }
interface Restricao { id: number; unidade: string; pavimento_id: number; pavimento: string; tipo: string }

const pavimentos = ref<Pavimento[]>([]);
const unidades = ref<Unidade[]>([]);
const pavimentosDestino = ref<PavimentoDestino[]>([]);
const restricoes = ref<Restricao[]>([]);
const erro = ref('');

const nova = ref({ unidade_nome: '', pavimento_catalogo_id: 0, tipo: 'obrigatorio' });

const colunasPanorama: Coluna[] = [
  { chave: 'nome_completo', rotulo: 'Pavimento', largura: '18rem' },
  { chave: 'padrao_1est', rotulo: 'Padrão 1 est.', editavel: true },
  { chave: 'padrao_2est', rotulo: 'Padrão 2 est.', editavel: true },
  { chave: 'esp_1est', rotulo: 'Espec. 1 est.', editavel: true },
  { chave: 'esp_2est', rotulo: 'Espec. 2 est.', editavel: true },
  { chave: 'fechada', rotulo: 'Fechadas', editavel: true },
  { chave: 'capacidade', rotulo: 'Estações' },
];

const capacidadeTotal = computed(() =>
  pavimentos.value.reduce((s, p) => s + (p.capacidade || 0), 0)
);

const rodapePanorama = computed(() => ({
  nome_completo: 'Total',
  capacidade: capacidadeTotal.value,
}));

async function carregar() {
  try {
    const [pan, res] = await Promise.all([
      api.get('/api/padroes/panorama'),
      api.get('/api/padroes/restricoes'),
    ]);
    pavimentos.value = pan.data.pavimentos;
    restricoes.value = res.data.restricoes;
    unidades.value = res.data.unidades;
    pavimentosDestino.value = res.data.pavimentos;
  } catch (e: any) {
    erro.value = e?.response?.data?.detail ?? 'Não foi possível carregar os padrões';
  }
}

async function comErro(acao: () => Promise<void>) {
  erro.value = '';
  try {
    await acao();
  } catch (e: any) {
    erro.value = e?.response?.data?.detail ?? e?.message ?? 'Operação recusada';
    await carregar();
  }
}

async function editarPanorama({ linha, chave, valor }: Alteracao) {
  await comErro(async () => {
    const { data } = await api.put('/api/padroes/panorama', [
      { pavimento_id: linha.id, contagens: { [chave]: valor } },
    ]);
    pavimentos.value = data.pavimentos;
  });
}

async function adicionarRestricao() {
  await comErro(async () => {
    const { data } = await api.post('/api/padroes/restricoes', { ...nova.value });
    restricoes.value = data.restricoes;
    nova.value = { unidade_nome: '', pavimento_catalogo_id: 0, tipo: nova.value.tipo };
  });
}

async function removerRestricao(r: Restricao) {
  await comErro(async () => {
    const { data } = await api.delete(`/api/padroes/restricoes/${r.id}`);
    restricoes.value = data.restricoes;
  });
}

onMounted(carregar);
</script>
