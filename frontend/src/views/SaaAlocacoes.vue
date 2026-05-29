<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-paper-text">Alocações</h1>
        <p class="text-sm text-gray-500">{{ store.alocacoes.length }} alocações registradas</p>
      </div>
      <div class="flex gap-3">
        <select v-model="filtros.dia" class="form-control !py-1.5 !text-sm w-36">
          <option value="">Todos os dias</option>
          <option v-for="d in DIAS" :key="d">{{ d }}</option>
        </select>
        <select v-model="filtros.turno" class="form-control !py-1.5 !text-sm w-32">
          <option value="">Todos os turnos</option>
          <option v-for="t in TURNOS" :key="t">{{ t }}</option>
        </select>
      </div>
    </div>

    <Card>
      <div v-if="alocacoesFiltradas.length === 0" class="text-center text-gray-400 py-12">
        <ClipboardDocumentListIcon class="h-12 w-12 mx-auto mb-3 opacity-30" />
        <p>Nenhuma alocação. Importe <code>alocacoes.csv</code> ou crie manualmente.</p>
      </div>
      <div v-else class="w-full overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-xs font-semibold text-gray-500 uppercase border-b border-gray-200 bg-gray-50">
            <tr>
              <th class="px-4 py-2 text-left">Grade</th>
              <th class="px-4 py-2 text-left">Especialidade</th>
              <th class="px-4 py-2 text-left">Profissional</th>
              <th class="px-4 py-2 text-left">Dia / Turno</th>
              <th class="px-4 py-2 text-left">Sala</th>
              <th class="px-4 py-2 text-left">Bloco</th>
              <th class="px-4 py-2 text-left">Status da Sala</th>
              <th class="px-4 py-2 text-left">Conflitos</th>
              <th class="px-4 py-2 text-left">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr
              v-for="aloc in alocacoesFiltradas"
              :key="aloc.id"
              class="hover:bg-gray-50"
            >
              <td class="px-4 py-3 text-xs text-gray-400">{{ aloc.grade_id }}</td>
              <td class="px-4 py-3 font-medium">{{ store.getGrade(aloc.grade_id)?.especialidade ?? '—' }}</td>
              <td class="px-4 py-3 text-gray-500">{{ store.getGrade(aloc.grade_id)?.profissional ?? '—' }}</td>
              <td class="px-4 py-3">{{ aloc.dia_semana }} / {{ aloc.turno }}</td>
              <td class="px-4 py-3 font-bold">{{ store.getSala(aloc.sala_id)?.numero ?? aloc.sala_id }}</td>
              <td class="px-4 py-3">{{ store.getSala(aloc.sala_id)?.bloco ?? '—' }}</td>
              <td class="px-4 py-3">
                <span class="px-2 py-0.5 rounded-full text-xs font-medium" :class="badgeStatus(store.getSala(aloc.sala_id)?.status ?? '')">
                  {{ store.getSala(aloc.sala_id)?.status ?? '—' }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span v-if="conflitosAloc(aloc.id).length" class="px-2 py-0.5 rounded bg-red-100 text-red-700 text-xs">
                  {{ conflitosAloc(aloc.id).length }} ⚠
                </span>
                <span v-else class="text-gray-300 text-xs">—</span>
              </td>
              <td class="px-4 py-3">
                <Button @click="abrirEdicao(aloc.id)" variant="warning" class="!py-1 !px-2 !text-xs">
                  Editar
                </Button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- Modal edição -->
    <Modal :show="!!alocacaoEditandoId" @close="alocacaoEditandoId = null">
      <template #header>Editar Alocação</template>
      <EditarAlocacaoDireta
        v-if="alocacaoEditandoId"
        :alocacao-id="alocacaoEditandoId"
        @salvo="alocacaoEditandoId = null"
        @cancelar="alocacaoEditandoId = null"
      />
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ClipboardDocumentListIcon } from '@heroicons/vue/24/outline';
import { useSaaStore } from '../stores/saa';
import Card from '../components/Card.vue';
import Button from '../components/Button.vue';
import Modal from '../components/Modal.vue';
import EditarAlocacaoDireta from '../components/EditarAlocacaoDireta.vue';

const store = useSaaStore();

const DIAS   = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
const TURNOS = ['Manhã', 'Tarde', 'Noite'];

const filtros = ref({ dia: '', turno: '' });
const alocacaoEditandoId = ref<string | null>(null);

const alocacoesFiltradas = computed(() => store.alocacoes.filter(a => {
  if (filtros.value.dia   && a.dia_semana !== filtros.value.dia)   return false;
  if (filtros.value.turno && a.turno      !== filtros.value.turno) return false;
  return true;
}));

function conflitosAloc(alocId: string) {
  return store.conflitos.filter(c => c.alocacao_id === alocId);
}

function badgeStatus(status: string) {
  switch (status) {
    case 'disponivel': return 'bg-green-100 text-green-700';
    case 'bloqueada':  return 'bg-red-100 text-red-700';
    case 'reforma':
    case 'manutencao': return 'bg-yellow-100 text-yellow-700';
    default:           return 'bg-gray-100 text-gray-700';
  }
}

function abrirEdicao(id: string) { alocacaoEditandoId.value = id; }
</script>
