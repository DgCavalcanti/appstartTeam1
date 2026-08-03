<template>
  <div class="overflow-x-auto border border-gray-200 rounded">
    <table class="w-full text-sm border-collapse">
      <thead>
        <tr class="bg-gray-50 text-xs text-gray-500">
          <th
            v-for="(coluna, c) in colunas"
            :key="coluna.chave"
            class="font-medium border-b border-gray-200 px-2 py-2 whitespace-nowrap"
            :class="c === 0 ? 'text-left sticky left-0 bg-gray-50 z-10' : 'text-center'"
            :style="coluna.largura ? { width: coluna.largura } : undefined"
          >
            <span
              v-for="(parte, k) in String(coluna.rotulo).split('\n')"
              :key="k"
              class="block leading-tight"
            >{{ parte }}</span>
          </th>
        </tr>
      </thead>

      <tbody>
        <template v-for="(linha, l) in linhas" :key="String(linha[chaveLinha])">
          <!-- Separador de grupo — surge quando a chave de grupo muda. -->
          <tr
            v-if="rotuloGrupo && (l === 0 || rotuloGrupo(linha) !== rotuloGrupo(linhas[l - 1]))"
            class="bg-gray-50"
          >
            <td
              :colspan="colunas.length"
              class="px-2 py-1 text-xs font-semibold text-gray-500 uppercase tracking-wide sticky left-0 bg-gray-50 z-10"
            >{{ rotuloGrupo(linha) }}</td>
          </tr>

          <tr class="border-b border-gray-100 transition-colors duration-150 hover:bg-gray-50/60">
            <td
              v-for="(coluna, c) in colunas"
              :key="coluna.chave"
              class="px-2 py-1"
              :class="[
                c === 0 ? 'text-left sticky left-0 bg-white z-10' : 'text-center',
                corDaCelula(linha, coluna),
              ]"
            >
              <!-- Célula editável -->
              <input
                v-if="coluna.editavel"
                type="number"
                :min="min"
                :max="max"
                :value="linha[coluna.chave]"
                :ref="el => registrar(el, l, c)"
                class="w-full min-w-[3rem] px-1 py-0.5 text-center tabular-nums bg-transparent rounded border border-transparent hover:border-gray-300 focus:border-paper-accent focus:bg-white focus:outline-none focus:ring-1 focus:ring-paper-accent/30 transition-all duration-150"
                @change="aoAlterar(linha, coluna, $event)"
                @focus="($event.target as HTMLInputElement).select()"
                @keydown="aoTeclar($event, l, c)"
                @paste="aoColar($event, l, c)"
              />

              <!-- Célula de leitura -->
              <span v-else :title="String(linha[coluna.chave] ?? '')" class="block truncate">
                <slot :name="`celula-${coluna.chave}`" :linha="linha">
                  {{ formatar(linha[coluna.chave]) }}
                </slot>
              </span>
            </td>
          </tr>
        </template>

        <tr v-if="!linhas.length">
          <td :colspan="colunas.length" class="px-2 py-6 text-center text-gray-400">
            Nada para exibir.
          </td>
        </tr>
      </tbody>

      <tfoot v-if="rodape">
        <tr class="bg-gray-50 font-medium">
          <td
            v-for="(coluna, c) in colunas"
            :key="coluna.chave"
            class="px-2 py-2 border-t border-gray-200 tabular-nums"
            :class="c === 0 ? 'text-left sticky left-0 bg-gray-50 z-10' : 'text-center'"
          >
            {{ formatar(rodape[coluna.chave]) }}
          </td>
        </tr>
      </tfoot>
    </table>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

export interface Coluna {
  chave: string;
  rotulo: string;
  /** Colunas editáveis viram campos numéricos navegáveis pelo teclado. */
  editavel?: boolean;
  largura?: string;
}

export interface Alteracao {
  linha: Record<string, any>;
  chave: string;
  valor: number;
}

const props = withDefaults(
  defineProps<{
    colunas: Coluna[];
    linhas: Record<string, any>[];
    chaveLinha?: string;
    rodape?: Record<string, any> | null;
    min?: number;
    max?: number;
    /** Recebe a linha e a coluna e devolve classes CSS — usado para realce. */
    corDaCelula?: (linha: Record<string, any>, coluna: Coluna) => string;
    /**
     * Rótulo do grupo de uma linha. Quando informado, uma linha separadora com
     * esse rótulo surge sempre que o grupo muda em relação à linha anterior.
     * As linhas já devem vir ordenadas pelo grupo.
     */
    rotuloGrupo?: (linha: Record<string, any>) => string;
  }>(),
  {
    chaveLinha: 'id',
    rodape: null,
    min: 0,
    max: undefined,
    corDaCelula: () => '',
    rotuloGrupo: undefined,
  }
);

const emit = defineEmits<{ (e: 'editar', alteracao: Alteracao): void }>();

/**
 * Mapa de campos por posição, para a navegação por teclado.
 * A chave é "linha:coluna" — mais simples de manter que uma matriz, já que as
 * colunas de leitura não registram campo nenhum.
 */
const campos = ref(new Map<string, HTMLInputElement>());

function registrar(el: unknown, linha: number, coluna: number) {
  const chave = `${linha}:${coluna}`;
  if (el instanceof HTMLInputElement) campos.value.set(chave, el);
  else campos.value.delete(chave);
}

function focar(linha: number, coluna: number): boolean {
  const campo = campos.value.get(`${linha}:${coluna}`);
  if (!campo) return false;
  campo.focus();
  return true;
}

/** Anda na direção pedida, pulando colunas que não são editáveis. */
function mover(linha: number, coluna: number, dl: number, dc: number) {
  let l = linha + dl;
  let c = coluna + dc;
  while (l >= 0 && l < props.linhas.length && c >= 0 && c < props.colunas.length) {
    if (focar(l, c)) return;
    l += dl;
    c += dc;
  }
}

function aoTeclar(evento: KeyboardEvent, linha: number, coluna: number) {
  const teclas: Record<string, [number, number]> = {
    ArrowUp: [-1, 0],
    ArrowDown: [1, 0],
    Enter: [1, 0],
    ArrowLeft: [0, -1],
    ArrowRight: [0, 1],
  };

  // Setas horizontais dentro de um campo com texto selecionado moveriam o
  // cursor; só navegamos quando não há o que percorrer dentro da célula.
  const alvo = evento.target as HTMLInputElement;
  if (evento.key === 'ArrowLeft' && alvo.selectionStart !== 0) return;
  if (evento.key === 'ArrowRight' && alvo.selectionEnd !== alvo.value.length) return;

  const passo = teclas[evento.key];
  if (!passo) return;

  evento.preventDefault();
  alvo.blur(); // dispara o @change antes de sair da célula
  mover(linha, coluna, passo[0], passo[1]);
}

function aoAlterar(linha: Record<string, any>, coluna: Coluna, evento: Event) {
  const alvo = evento.target as HTMLInputElement;
  const valor = Number(alvo.value);

  if (!Number.isFinite(valor) || valor < props.min || (props.max !== undefined && valor > props.max)) {
    // Valor inválido: devolve o campo ao que estava, sem emitir.
    alvo.value = String(linha[coluna.chave] ?? 0);
    return;
  }
  if (valor === linha[coluna.chave]) return;

  emit('editar', { linha, chave: coluna.chave, valor });
}

/**
 * Colar do Excel: o conteúdo vem como TSV, então uma seleção retangular
 * preenche várias células a partir da que está focada.
 */
function aoColar(evento: ClipboardEvent, linha: number, coluna: number) {
  const texto = evento.clipboardData?.getData('text/plain') ?? '';
  if (!texto.includes('\t') && !texto.includes('\n')) return; // valor único: fluxo normal

  evento.preventDefault();
  const matriz = texto
    .replace(/\r/g, '')
    .split('\n')
    .filter(l => l.length)
    .map(l => l.split('\t'));

  matriz.forEach((celulas, dl) => {
    celulas.forEach((bruto, dc) => {
      const alvoLinha = props.linhas[linha + dl];
      const alvoColuna = props.colunas[coluna + dc];
      if (!alvoLinha || !alvoColuna?.editavel) return;

      const valor = Number(bruto.trim().replace(',', '.'));
      if (!Number.isFinite(valor) || valor < props.min) return;
      if (props.max !== undefined && valor > props.max) return;
      if (valor === alvoLinha[alvoColuna.chave]) return;

      emit('editar', { linha: alvoLinha, chave: alvoColuna.chave, valor });
    });
  });
}

function formatar(valor: unknown): string {
  if (valor === null || valor === undefined || valor === '') return '';
  return typeof valor === 'number' ? valor.toLocaleString('pt-BR') : String(valor);
}
</script>
