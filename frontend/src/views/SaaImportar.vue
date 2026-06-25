<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-paper-text">Importar Dados</h1>
      <p class="text-sm text-gray-500 mt-1">
        Envie os CSVs do sistema aqui — Grades, Consultas, Salas, Restrições e Alocações.
        Os conflitos e indicadores são recalculados automaticamente após cada importação.
      </p>
    </div>

    <!-- Cards de importação por tipo -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
      <ImportCard
        titulo="Grades"
        arquivo="grades.csv"
        descricao="Grade de atendimento exportada do AGHU"
        :icone="AcademicCapIcon"
        :resultado="resultados.grades"
        :carregando="carregando.grades"
        @importar="(arquivo: File) => importar('grades', arquivo)"
      />
      <ImportCard
        titulo="Consultas"
        arquivo="consultas.csv"
        descricao="Consultas ambulatoriais exportadas do AGHU"
        :icone="CalendarDaysIcon"
        :resultado="resultados.consultas"
        :carregando="carregando.consultas"
        @importar="(arquivo: File) => importar('consultas', arquivo)"
      />
      <ImportCard
        titulo="Salas"
        arquivo="salas.csv"
        descricao="Colunas obrigatórias: id, numero, bloco, status. Opcionais: andar, acessibilidade, equipamentos (separados por ;), especialidade_preferencial"
        :icone="BuildingOfficeIcon"
        :resultado="resultados.salas"
        :carregando="carregando.salas"
        @importar="(arquivo: File) => importar('salas', arquivo)"
      />
      <ImportCard
        titulo="Restrições"
        arquivo="restricoes.csv"
        descricao="Colunas obrigatórias: id, sala_id, tipo, valor"
        :icone="ShieldExclamationIcon"
        :resultado="resultados.restricoes"
        :carregando="carregando.restricoes"
        @importar="(arquivo: File) => importar('restricoes', arquivo)"
      />
      <ImportCard
        titulo="Alocações"
        arquivo="alocacoes.csv"
        descricao="Colunas obrigatórias: id, grade_id, sala_id, dia_semana, turno"
        :icone="ClipboardDocumentListIcon"
        :resultado="resultados.alocacoes"
        :carregando="carregando.alocacoes"
        @importar="(arquivo: File) => importar('alocacoes', arquivo)"
      />
    </div>

    <!-- Situação atual dos dados carregados -->
    <Card>
      <template #header>
        <h2 class="font-semibold">Situação Atual dos Dados</h2>
      </template>
      <div class="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
        <div class="p-4 bg-gray-50 rounded-lg">
          <div class="text-2xl font-bold text-paper-primary">{{ store.grades.length }}</div>
          <div class="text-xs text-gray-500 mt-1">Grades</div>
        </div>
        <div class="p-4 bg-gray-50 rounded-lg">
          <div class="text-2xl font-bold text-paper-primary">{{ aghuStore.capacidade?.total_consultas ?? 0 }}</div>
          <div class="text-xs text-gray-500 mt-1">Consultas</div>
        </div>
        <div class="p-4 bg-gray-50 rounded-lg">
          <div class="text-2xl font-bold text-paper-primary">{{ store.salas.length }}</div>
          <div class="text-xs text-gray-500 mt-1">Salas</div>
        </div>
        <div class="p-4 bg-gray-50 rounded-lg">
          <div class="text-2xl font-bold text-paper-primary">{{ store.restricoes.length }}</div>
          <div class="text-xs text-gray-500 mt-1">Restrições</div>
        </div>
        <div class="p-4 bg-gray-50 rounded-lg">
          <div class="text-2xl font-bold text-paper-primary">{{ store.alocacoes.length }}</div>
          <div class="text-xs text-gray-500 mt-1">Alocações</div>
        </div>
      </div>
      <div class="mt-4 pt-4 border-t border-gray-100">
        <div
          v-if="store.conflitos.length > 0"
          class="flex items-center gap-2 text-sm text-red-600"
        >
          <ExclamationTriangleIcon class="h-4 w-4" />
          {{ store.conflitos.length }} conflito(s) detectado(s) — acesse o Painel para detalhes.
        </div>
        <div v-else class="flex items-center gap-2 text-sm text-green-600">
          <CheckCircleIcon class="h-4 w-4" />
          Nenhum conflito detectado nos dados carregados.
        </div>
      </div>
    </Card>

    <!-- Exemplo de CSV -->
    <Card class="mt-6">
      <template #header>
        <h2 class="font-semibold">Exemplos de formato CSV</h2>
      </template>
      <div class="space-y-4 text-xs font-mono">
        <div>
          <p class="text-gray-500 font-sans font-medium mb-1">salas.csv</p>
          <pre class="bg-gray-50 p-3 rounded overflow-x-auto text-gray-700">id,numero,bloco,andar,status,acessibilidade,equipamentos,especialidade_preferencial
S001,101,A,1,disponivel,true,ECG;Monitor,Cardiologia
S002,102,A,1,disponivel,false,,Geral</pre>
        </div>
        <div>
          <p class="text-gray-500 font-sans font-medium mb-1">alocacoes.csv</p>
          <pre class="bg-gray-50 p-3 rounded overflow-x-auto text-gray-700">id,grade_id,sala_id,dia_semana,turno
A001,G001,S001,Segunda,Manhã</pre>
        </div>
      </div>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue';
import {
  BuildingOfficeIcon, ShieldExclamationIcon,
  ClipboardDocumentListIcon, ExclamationTriangleIcon, CheckCircleIcon,
  AcademicCapIcon, CalendarDaysIcon,
} from '@heroicons/vue/24/outline';
import { useSaaStore } from '../stores/saa';
import { useAghuStore } from '../stores/aghu';
import { useToast } from 'vue-toastification';
import Card from '../components/Card.vue';
import ImportCard from '../components/ImportCard.vue';

const store = useSaaStore();
const aghuStore = useAghuStore();
const toast  = useToast();

const resultados = reactive<Record<string, { ok: boolean; mensagem: string } | null>>({
  grades: null, consultas: null, salas: null, restricoes: null, alocacoes: null,
});

// CORRIGIDO (auditoria técnica): não havia nenhum estado de carregamento
// exposto por arquivo/card durante a importação — o usuário só via o aviso
// final (sucesso/erro), sem indicação de que o CSV ainda estava sendo
// processado. `carregando[tipo]` liga o spinner em ImportCard.vue do
// início ao fim de cada importação, sem substituir o aviso existente.
const carregando = reactive<Record<string, boolean>>({
  grades: false, consultas: false, salas: false, restricoes: false, alocacoes: false,
});

/**
 * Dispatcher de importação — chama a função correta do store e exibe
 * feedback via toast.
 *
 * Todos os tipos (Grades/Consultas via stores/aghu.ts; Salas/Restrições/
 * Alocações via stores/saa.ts) fazem upload real do arquivo (multipart)
 * para o backend, que persiste o CSV no caminho lido pelas demais telas.
 */
async function importar(tipo: string, arquivo: File) {
  carregando[tipo] = true;
  try {
    let resultado: { ok: boolean; mensagem: string };

    if (tipo === 'grades' || tipo === 'consultas') {
      const r = tipo === 'grades'
        ? await aghuStore.importarGradesAghu(arquivo)
        : await aghuStore.importarConsultasAghu(arquivo);
      if (r) {
        const avisos = r.avisos.length ? ` — ${r.avisos.join('; ')}` : '';
        resultado = { ok: true, mensagem: `${r.linhas_validas} válida(s) / ${r.linhas_lidas} lida(s)${avisos}` };
        if (tipo === 'grades') await store.buscarGrades();
      } else {
        resultado = { ok: false, mensagem: aghuStore.erro ?? 'Erro ao importar arquivo.' };
      }
    } else {
      const r = tipo === 'salas'
        ? await store.importarSalas(arquivo)
        : tipo === 'restricoes'
          ? await store.importarRestricoes(arquivo)
          : tipo === 'alocacoes'
            ? await store.importarAlocacoes(arquivo)
            : null;
      if (tipo !== 'salas' && tipo !== 'restricoes' && tipo !== 'alocacoes') return;
      if (r) {
        const avisos = r.avisos.length ? ` — ${r.avisos.join('; ')}` : '';
        resultado = { ok: true, mensagem: `${r.linhas_validas} válida(s) / ${r.linhas_lidas} lida(s)${avisos}` };
      } else {
        resultado = { ok: false, mensagem: store.erro ?? 'Erro ao importar arquivo.' };
      }
    }

    resultados[tipo] = resultado;
    if (resultado.ok) {
      toast.success(`✓ ${resultado.mensagem}`);
    } else {
      toast.error(`✗ ${resultado.mensagem}`);
    }
  } finally {
    carregando[tipo] = false;
  }
}
</script>
