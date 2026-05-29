<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-paper-text">Grades de Atendimento</h1>
        <p class="text-sm text-gray-500">{{ store.grades.length }} grades carregadas</p>
      </div>
      <div class="flex flex-wrap gap-3">
        <input v-model="filtros.especialidade" type="text" placeholder="Filtrar por especialidade" class="form-control !py-1.5 !text-sm w-48" />
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
      <div v-if="gradesFiltradas.length === 0" class="text-center text-gray-400 py-12">
        <AcademicCapIcon class="h-12 w-12 mx-auto mb-3 opacity-30" />
        <p>Nenhuma grade encontrada. Importe um arquivo <code>grades.csv</code>.</p>
      </div>
      <div v-else class="w-full overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-xs font-semibold text-gray-500 uppercase border-b border-gray-200 bg-gray-50">
            <tr>
              <th class="px-4 py-2 text-left">Especialidade</th>
              <th class="px-4 py-2 text-left">Profissional</th>
              <th class="px-4 py-2 text-left">Dia</th>
              <th class="px-4 py-2 text-left">Turno</th>
              <th class="px-4 py-2 text-center">Salas Necessárias</th>
              <th class="px-4 py-2 text-left">Sala Alocada</th>
              <th class="px-4 py-2 text-left">Status</th>
              <th class="px-4 py-2 text-left">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr
              v-for="grade in gradesFiltradas"
              :key="grade.id"
              class="hover:bg-gray-50 transition-colors"
            >
              <td class="px-4 py-3 font-medium">{{ grade.especialidade }}</td>
              <td class="px-4 py-3 text-gray-500">{{ grade.profissional }}</td>
              <td class="px-4 py-3">{{ grade.dia_semana }}</td>
              <td class="px-4 py-3">
                <span class="px-2 py-0.5 rounded-full text-xs font-medium" :class="badgeTurno(grade.turno)">
                  {{ grade.turno }}
                </span>
              </td>
              <td class="px-4 py-3 text-center">{{ grade.qtd_salas_necessarias }}</td>
              <td class="px-4 py-3">
                <span v-if="store.getAlocacaoPorGrade(grade.id)">
                  Sala {{ store.getSala(store.getAlocacaoPorGrade(grade.id)!.sala_id)?.numero ?? '?' }}
                </span>
                <span v-else class="text-red-500 font-semibold">Sem sala ⚠</span>
              </td>
              <td class="px-4 py-3">
                <span
                  v-if="store.getConflitosParaGrade(grade.id).length > 0"
                  class="px-2 py-0.5 rounded bg-red-100 text-red-700 text-xs"
                >{{ store.getConflitosParaGrade(grade.id).length }} conflito(s)</span>
                <span v-else class="px-2 py-0.5 rounded bg-green-100 text-green-700 text-xs">OK</span>
              </td>
              <td class="px-4 py-3">
                <Button @click="editarAlocacaoGrade(grade)" variant="warning" size="sm" class="!py-1 !px-2 !text-xs">
                  Editar Sala
                </Button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- Modal edição de alocação -->
    <Modal :show="!!gradeEditando" @close="gradeEditando = null">
      <template #header>Editar Alocação — {{ gradeEditando?.especialidade }}</template>
      <EditarAlocacao
        v-if="gradeEditando"
        :grade="gradeEditando"
        @salvo="gradeEditando = null"
        @cancelar="gradeEditando = null"
      />
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { AcademicCapIcon } from '@heroicons/vue/24/outline';
import { useSaaStore, type Grade } from '../stores/saa';
import Card from '../components/Card.vue';
import Button from '../components/Button.vue';
import Modal from '../components/Modal.vue';
import EditarAlocacao from '../components/EditarAlocacao.vue';

const store = useSaaStore();

const DIAS   = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
const TURNOS = ['Manhã', 'Tarde', 'Noite'];

const filtros = ref({ especialidade: '', dia: '', turno: '' });
const gradeEditando = ref<Grade | null>(null);

const gradesFiltradas = computed(() => store.grades.filter(g => {
  if (filtros.value.especialidade && !g.especialidade.toLowerCase().includes(filtros.value.especialidade.toLowerCase())) return false;
  if (filtros.value.dia   && g.dia_semana !== filtros.value.dia)   return false;
  if (filtros.value.turno && g.turno      !== filtros.value.turno) return false;
  return true;
}));

function badgeTurno(turno: string) {
  switch (turno) {
    case 'Manhã':  return 'bg-blue-100 text-blue-700';
    case 'Tarde':  return 'bg-orange-100 text-orange-700';
    case 'Noite':  return 'bg-purple-100 text-purple-700';
    default:       return 'bg-gray-100 text-gray-700';
  }
}

function editarAlocacaoGrade(grade: Grade) {
  gradeEditando.value = grade;
}
</script>
