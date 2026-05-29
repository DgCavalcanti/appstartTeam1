<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-paper-text">Importar Dados (CSV)</h1>
      <p class="text-sm text-gray-500 mt-1">
        Carregue os arquivos CSV para alimentar o sistema. Os conflitos são detectados automaticamente após cada importação.
      </p>
    </div>

    <!-- Cards de importação por tipo -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
      <ImportCard
        titulo="Grades de Atendimento"
        arquivo="grades.csv"
        descricao="Colunas obrigatórias: id, especialidade, profissional, dia_semana, turno, qtd_salas_necessarias"
        :icone="AcademicCapIcon"
        :resultado="resultados.grades"
        @importar="(csv: string) => importar('grades', csv)"
      />
      <ImportCard
        titulo="Salas Ambulatoriais"
        arquivo="salas.csv"
        descricao="Colunas obrigatórias: id, numero, bloco, status. Opcionais: andar, acessibilidade, equipamentos (separados por ;), especialidade_preferencial"
        :icone="BuildingOfficeIcon"
        :resultado="resultados.salas"
        @importar="(csv: string) => importar('salas', csv)"
      />
      <ImportCard
        titulo="Restrições"
        arquivo="restricoes.csv"
        descricao="Colunas obrigatórias: id, sala_id, tipo, valor"
        :icone="ShieldExclamationIcon"
        :resultado="resultados.restricoes"
        @importar="(csv: string) => importar('restricoes', csv)"
      />
      <ImportCard
        titulo="Alocações"
        arquivo="alocacoes.csv"
        descricao="Colunas obrigatórias: id, grade_id, sala_id, dia_semana, turno"
        :icone="ClipboardDocumentListIcon"
        :resultado="resultados.alocacoes"
        @importar="(csv: string) => importar('alocacoes', csv)"
      />
    </div>

    <!-- Situação atual dos dados carregados -->
    <Card>
      <template #header>
        <h2 class="font-semibold">Situação Atual dos Dados</h2>
      </template>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
        <div class="p-4 bg-gray-50 rounded-lg">
          <div class="text-2xl font-bold text-paper-primary">{{ store.grades.length }}</div>
          <div class="text-xs text-gray-500 mt-1">Grades</div>
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
          {{ store.conflitos.length }} conflito(s) detectado(s) — acesse o Dashboard para detalhes.
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
          <p class="text-gray-500 font-sans font-medium mb-1">grades.csv</p>
          <pre class="bg-gray-50 p-3 rounded overflow-x-auto text-gray-700">id,especialidade,profissional,dia_semana,turno,qtd_salas_necessarias
G001,Cardiologia,Dr. Silva,Segunda,Manhã,2
G002,Ortopedia,Dr. Souza,Terça,Tarde,1</pre>
        </div>
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
  AcademicCapIcon, BuildingOfficeIcon, ShieldExclamationIcon,
  ClipboardDocumentListIcon, ExclamationTriangleIcon, CheckCircleIcon
} from '@heroicons/vue/24/outline';
import { useSaaStore } from '../stores/saa';
import { useToast } from 'vue-toastification';
import Card from '../components/Card.vue';
import ImportCard from '../components/ImportCard.vue';

const store = useSaaStore();
const toast  = useToast();

const resultados = reactive<Record<string, { ok: boolean; mensagem: string } | null>>({
  grades: null, salas: null, restricoes: null, alocacoes: null,
});

/**
 * Dispatcher de importação — chama a função correta do store
 * e exibe feedback via toast.
 */
function importar(tipo: string, csv: string) {
  let resultado: { ok: boolean; mensagem: string };
  switch (tipo) {
    case 'grades':    resultado = store.importarGrades(csv);    break;
    case 'salas':     resultado = store.importarSalas(csv);     break;
    case 'restricoes': resultado = store.importarRestricoes(csv); break;
    case 'alocacoes': resultado = store.importarAlocacoes(csv); break;
    default: return;
  }
  resultados[tipo] = resultado;
  if (resultado.ok) {
    toast.success(`✓ ${resultado.mensagem}`);
  } else {
    toast.error(`✗ ${resultado.mensagem}`);
  }
}
</script>
