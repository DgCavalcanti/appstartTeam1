<template>
  <div>
    <div class="flex flex-wrap items-center gap-2 mb-3">
      <input
        v-model="busca"
        type="search"
        placeholder="Buscar clínica…"
        class="px-3 py-1.5 text-sm border border-gray-300 rounded w-52 focus:outline-none focus:border-paper-primary"
      />
      <select
        v-model="filtroBloco"
        class="px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:border-paper-primary"
      >
        <option value="">Todos os blocos</option>
        <option v-for="b in blocos" :key="b" :value="b">{{ b }}</option>
      </select>
      <select
        v-model="filtroPavimento"
        class="px-3 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:border-paper-primary"
      >
        <option value="">Todos os pavimentos</option>
        <option v-for="p in pavimentos" :key="p" :value="p">{{ p }}</option>
      </select>
      <button
        v-if="temFiltro"
        class="text-xs text-paper-info hover:underline"
        @click="limpar"
      >limpar</button>
      <span class="text-xs text-gray-500 ml-auto">
        Mostrando {{ filtradas.length }} de {{ linhas.length }}
      </span>
    </div>

    <slot :filtradas="filtradas" />
  </div>
</template>

<script
  setup
  lang="ts"
  generic="T extends { nome: string; bloco?: string | null; pavimento?: string | null }"
>
import { computed, ref } from 'vue';

// Genérico em T para o slot devolver as linhas com o tipo concreto de quem
// chama, em vez de um tipo achatado — assim `filtradas` mantém todos os campos.
const props = defineProps<{ linhas: T[] }>();

const busca = ref('');
const filtroBloco = ref('');
const filtroPavimento = ref('');

const temFiltro = computed(
  () => !!busca.value || !!filtroBloco.value || !!filtroPavimento.value
);

/** Remove acentos e baixa a caixa, para a busca casar "oftalmologia" etc. */
function normalizar(texto: string): string {
  return texto
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim();
}

/** Distintos, preservando ordem de aparição. */
function distintos(seletor: (l: T) => string | null | undefined): string[] {
  const vistos = new Set<string>();
  for (const l of props.linhas) {
    const v = seletor(l);
    if (v) vistos.add(v);
  }
  return [...vistos].sort();
}

const blocos = computed(() => distintos(l => l.bloco));
const pavimentos = computed(() => distintos(l => l.pavimento));

/**
 * Bloco e pavimento são filtros independentes que combinam (E). Escolher só o
 * bloco mostra todos os andares dele; escolher só o pavimento mostra aquele
 * andar em todos os blocos; os dois juntos cruzam. A busca casa o nome da
 * clínica, ignorando acento e caixa.
 */
const filtradas = computed(() => {
  const termo = normalizar(busca.value);
  return props.linhas.filter(l => {
    if (filtroBloco.value && l.bloco !== filtroBloco.value) return false;
    if (filtroPavimento.value && l.pavimento !== filtroPavimento.value) return false;
    if (termo && !normalizar(l.nome).includes(termo)) return false;
    return true;
  });
});

function limpar() {
  busca.value = '';
  filtroBloco.value = '';
  filtroPavimento.value = '';
}
</script>
