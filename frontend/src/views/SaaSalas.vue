<template>
  <div>
    <div class="flex flex-wrap items-center justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-paper-text">Salas Ambulatoriais</h1>
        <p class="text-sm text-gray-500">{{ store.salas.length }} salas cadastradas</p>
      </div>
      <div class="flex flex-wrap gap-3">
        <input v-model="filtros.busca" type="text" placeholder="Buscar por número ou bloco" class="form-control !py-1.5 !text-sm w-48" />
        <select v-model="filtros.status" class="form-control !py-1.5 !text-sm w-36">
          <option value="">Todos os status</option>
          <option v-for="s in STATUS_SALAS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
        <select v-model="filtros.bloco" class="form-control !py-1.5 !text-sm w-32">
          <option value="">Todos os blocos</option>
          <option v-for="b in blocos" :key="b">{{ b }}</option>
        </select>
      </div>
    </div>

    <Card>
      <div v-if="salasFiltradas.length === 0" class="text-center text-gray-400 py-12">
        <BuildingOfficeIcon class="h-12 w-12 mx-auto mb-3 opacity-30" />
        <p>Nenhuma sala encontrada. Importe um arquivo <code>salas.csv</code>.</p>
      </div>
      <div v-else class="w-full overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-xs font-semibold text-gray-500 uppercase border-b border-gray-200 bg-gray-50">
            <tr>
              <th class="px-4 py-2 text-left">Nº</th>
              <th class="px-4 py-2 text-left">Bloco</th>
              <th class="px-4 py-2 text-left">Andar</th>
              <th class="px-4 py-2 text-left">Status</th>
              <th class="px-4 py-2 text-left">Especialidade Pref.</th>
              <th class="px-4 py-2 text-left">Equipamentos</th>
              <th class="px-4 py-2 text-center">Acessível</th>
              <th class="px-4 py-2 text-left">Conflitos</th>
              <th class="px-4 py-2 text-left">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr
              v-for="sala in salasFiltradas"
              :key="sala.id"
              class="hover:bg-gray-50 transition-colors"
              :class="sala.status === 'bloqueada' || sala.status === 'reforma' || sala.status === 'manutencao' ? 'opacity-70' : ''"
            >
              <td class="px-4 py-3 font-bold">{{ sala.numero }}</td>
              <td class="px-4 py-3">{{ sala.bloco }}</td>
              <td class="px-4 py-3 text-gray-500">{{ sala.andar || '—' }}</td>
              <td class="px-4 py-3">
                <span class="px-2 py-0.5 rounded-full text-xs font-medium" :class="badgeStatus(sala.status)">
                  {{ STATUS_LABEL[sala.status] ?? sala.status }}
                </span>
              </td>
              <td class="px-4 py-3">{{ sala.especialidade_preferencial || '—' }}</td>
              <td class="px-4 py-3">
                <span v-if="sala.equipamentos.length === 0" class="text-gray-300">—</span>
                <span v-else class="flex flex-wrap gap-1">
                  <span v-for="eq in sala.equipamentos" :key="eq"
                    class="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-xs">{{ eq }}</span>
                </span>
              </td>
              <td class="px-4 py-3 text-center">
                <span v-if="sala.acessibilidade" class="text-green-600 font-bold">✓</span>
                <span v-else class="text-gray-300">—</span>
              </td>
              <td class="px-4 py-3">
                <span v-if="store.getConflitosParaSala(sala.id).length > 0"
                  class="px-2 py-0.5 rounded bg-red-100 text-red-700 text-xs font-medium">
                  {{ store.getConflitosParaSala(sala.id).length }} ⚠
                </span>
                <span v-else class="text-gray-300 text-xs">—</span>
              </td>
              <td class="px-4 py-3">
                <Button @click="salaSelecionada = sala" variant="info" class="!py-1 !px-2 !text-xs">
                  Detalhes
                </Button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>

    <!-- Modal detalhe -->
    <Modal :show="!!salaSelecionada" @close="salaSelecionada = null">
      <template #header>Detalhe — Sala {{ salaSelecionada?.numero }}</template>
      <DetalhesSala v-if="salaSelecionada" :sala="salaSelecionada" @fechar="salaSelecionada = null" />
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { BuildingOfficeIcon } from '@heroicons/vue/24/outline';
import { useSaaStore, type Sala } from '../stores/saa';
import Card from '../components/Card.vue';
import Button from '../components/Button.vue';
import Modal from '../components/Modal.vue';
import DetalhesSala from '../components/DetalhesSala.vue';

const store = useSaaStore();

const STATUS_SALAS = [
  { value: 'disponivel', label: 'Disponível' },
  { value: 'bloqueada',  label: 'Bloqueada' },
  { value: 'reforma',    label: 'Em Reforma' },
  { value: 'manutencao', label: 'Em Manutenção' },
  { value: 'ocupada',    label: 'Ocupada' },
];
const STATUS_LABEL: Record<string, string> = {
  disponivel: 'Disponível',
  bloqueada:  'Bloqueada',
  reforma:    'Em Reforma',
  manutencao: 'Manutenção',
  ocupada:    'Ocupada',
};

const filtros = ref({ busca: '', status: '', bloco: '' });
const salaSelecionada = ref<Sala | null>(null);

const blocos = computed(() => [...new Set(store.salas.map(s => s.bloco))].sort());

const salasFiltradas = computed(() => store.salas.filter(s => {
  if (filtros.value.busca && !s.numero.includes(filtros.value.busca) && !s.bloco.toLowerCase().includes(filtros.value.busca.toLowerCase())) return false;
  if (filtros.value.status && s.status !== filtros.value.status) return false;
  if (filtros.value.bloco  && s.bloco  !== filtros.value.bloco)  return false;
  return true;
}));

function badgeStatus(status: string) {
  switch (status) {
    case 'disponivel': return 'bg-green-100 text-green-700';
    case 'bloqueada':  return 'bg-red-100 text-red-700';
    case 'reforma':    return 'bg-yellow-100 text-yellow-700';
    case 'manutencao': return 'bg-orange-100 text-orange-700';
    case 'ocupada':    return 'bg-blue-100 text-blue-700';
    default:           return 'bg-gray-100 text-gray-700';
  }
}
</script>
