<template>
  <div class="space-y-6 animate-fade-in-up">
    <section class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
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
    <section class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
      <h3 class="text-lg font-semibold text-paper-text mb-1">
        Panorama de salas
        <span class="text-sm font-normal text-gray-500">— {{ capacidadeTotal }} estações por turno</span>
      </h3>
      <p class="text-sm text-gray-500 mb-4">
        Quantas salas de cada tipo há em cada pavimento do HC. A capacidade em
        estações é calculada — uma sala de 2 estações vale 2.
      </p>

      <div v-if="pavimentos.length" class="overflow-x-auto">
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
            <template v-for="(p, i) in pavimentos" :key="p.id">
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

    <!-- ── Restrições padrão ───────────────────────────────────────────── -->
    <section class="bg-white rounded-lg border border-paper-line shadow-paper p-6 transition-shadow duration-300 hover:shadow-md">
      <h3 class="text-lg font-semibold text-paper-text mb-1">Obrigatoriedades e preferências padrão</h3>
      <p class="text-sm text-gray-500 mb-4">
        <strong>Obrigatória</strong> trava a clínica num pavimento;
        <strong>preferencial</strong> é um puxão que cede se não couber. Só as
        clínicas que participam de um cenário herdam a restrição na prática.
      </p>

      <div class="flex flex-wrap items-end gap-3 mb-5">
        <div class="flex-1 min-w-[14rem]">
          <label class="form-label">Clínica</label>
          <select v-model="nova.unidade" class="form-control">
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
          :disabled="!nova.unidade || !nova.pavimento_catalogo_id"
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

import { type Alteracao } from '../components/PlanilhaEditavel.vue';
import api from '../services/api';

interface Pavimento {
  id: number; bloco: string; nome: string; nome_completo: string; andar: number;
  padrao_1est: number; padrao_2est: number; esp_1est: number; esp_2est: number;
  fechada: number; capacidade: number;
  [chave: string]: string | number;
}
interface Unidade { nome: string; participa_default: boolean }
interface PavimentoDestino { id: number; nome_completo: string }
interface Restricao { id: number; unidade: string; pavimento_catalogo_id: number; pavimento: string; tipo: string }

const pavimentos = ref<Pavimento[]>([]);
const unidades = ref<Unidade[]>([]);
const pavimentosDestino = ref<PavimentoDestino[]>([]);
const restricoes = ref<Restricao[]>([]);
const erro = ref('');

const nova = ref({ unidade: '', pavimento_catalogo_id: 0, tipo: 'obrigatorio' });

/** Os quatro tipos de sala que entram na capacidade, mais as fechadas. */
const CAMPOS_SALA = ['padrao_1est', 'padrao_2est', 'esp_1est', 'esp_2est', 'fechada'] as const;

const capacidadeTotal = computed(() =>
  pavimentos.value.reduce((s, p) => s + (p.capacidade || 0), 0)
);

/**
 * A lista já vem agrupada por andar (o backend ordena assim); aqui só
 * decidimos onde começa cada grupo, comparando com o pavimento anterior.
 */
function mudaDeAndar(indice: number): boolean {
  if (indice === 0) return true;
  return pavimentos.value[indice].andar !== pavimentos.value[indice - 1].andar;
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

async function carregar() {
  try {
    const [pan, res] = await Promise.all([
      api.get('/api/cenarios/padroes'),
      api.get('/api/cenarios/regras-padrao'),
    ]);
    pavimentos.value = pan.data.pavimentos;
    restricoes.value = res.data.regras;
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
    const { data } = await api.put('/api/cenarios/padroes', [
      { pavimento_id: linha.id, contagens: { [chave]: valor } },
    ]);
    pavimentos.value = data.pavimentos;
  });
}

async function adicionarRestricao() {
  await comErro(async () => {
    const { data } = await api.post('/api/cenarios/regras-padrao', { ...nova.value });
    restricoes.value = data.regras;
    nova.value = { unidade: '', pavimento_catalogo_id: 0, tipo: nova.value.tipo };
  });
}

async function removerRestricao(r: Restricao) {
  await comErro(async () => {
    // O DELETE devolve só { removida }; tiramos a regra da lista local.
    await api.delete(`/api/cenarios/regras-padrao/${r.id}`);
    restricoes.value = restricoes.value.filter(x => x.id !== r.id);
  });
}

onMounted(carregar);
</script>
