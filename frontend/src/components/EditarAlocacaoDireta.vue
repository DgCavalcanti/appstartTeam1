<template>
  <div v-if="alocacao && grade">
    <!-- Resumo -->
    <div class="mb-4 p-3 bg-gray-50 rounded text-sm">
      <p class="font-medium">{{ grade.especialidade }} — {{ grade.profissional }}</p>
      <p class="text-gray-500">{{ alocacao.dia_semana }} / {{ alocacao.turno }}</p>
    </div>

    <div class="mb-4 p-3 bg-gray-50 rounded text-sm">
      <p class="text-gray-500 mb-1">Sala atual</p>
      <p class="font-bold text-lg">{{ store.getSala(alocacao.sala_id)?.numero ?? alocacao.sala_id }}</p>
    </div>

    <div class="form-group">
      <label class="form-label">Nova sala</label>
      <select v-model="novaSalaId" class="form-control">
        <option value="">— Selecione —</option>
        <option v-for="sala in store.salas" :key="sala.id" :value="sala.id">
          Sala {{ sala.numero }} ({{ sala.bloco }}) — {{ sala.status }}
        </option>
      </select>
    </div>

    <!-- Alertas prévia -->
    <div v-if="conflitosPrevistos.length > 0" class="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded text-sm">
      <p class="font-semibold text-yellow-800 mb-1">
        <ExclamationTriangleIcon class="h-4 w-4 inline" />
        {{ conflitosPrevistos.length }} alerta(s)
      </p>
      <ul class="space-y-1 text-yellow-700">
        <li v-for="c in conflitosPrevistos" :key="c.id">
          <strong class="uppercase text-xs">{{ c.gravidade }}:</strong> {{ c.descricao }}
        </li>
      </ul>
    </div>

    <div v-if="exigeJustificativa" class="form-group">
      <label class="form-label text-red-700">Justificativa (obrigatória)</label>
      <textarea v-model="justificativa" class="form-control" rows="3" />
    </div>

    <div class="flex justify-end gap-3 mt-4">
      <Button variant="default" @click="$emit('cancelar')">Cancelar</Button>
      <Button variant="primary"
        :disabled="!novaSalaId || (exigeJustificativa && !justificativa.trim())"
        @click="salvar">
        Confirmar
      </Button>
    </div>
  </div>
  <div v-else class="text-red-500 text-sm">Alocação não encontrada.</div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ExclamationTriangleIcon } from '@heroicons/vue/24/outline';
import { useSaaStore, type Alocacao } from '../stores/saa';
import { useAuthStore } from '../stores/auth';
import { useToast } from 'vue-toastification';
import Button from './Button.vue';

const props = defineProps<{ alocacaoId: string }>();
const emit  = defineEmits(['salvo', 'cancelar']);

const store = useSaaStore();
const auth  = useAuthStore();
const toast = useToast();

const novaSalaId    = ref('');
const justificativa = ref('');

const alocacao = computed(() => store.alocacoes.find((a: Alocacao) => a.id === props.alocacaoId));
const grade    = computed(() => alocacao.value ? store.getGrade(alocacao.value.grade_id) : undefined);

const conflitosPrevistos = computed(() => {
  if (!novaSalaId.value || !grade.value) return [];
  const sala = store.getSala(novaSalaId.value);
  if (!sala) return [];
  const r: any[] = [];
  if (sala.status === 'bloqueada' || sala.status === 'reforma' || sala.status === 'manutencao')
    r.push({ id: 'p1', gravidade: 'critico', descricao: `Sala ${sala.numero} está ${sala.status}.` });
  if (sala.especialidade_preferencial && sala.especialidade_preferencial !== grade.value.especialidade && sala.especialidade_preferencial !== 'Geral')
    r.push({ id: 'p2', gravidade: 'operacional', descricao: `Sala preferencial para ${sala.especialidade_preferencial}.` });
  const dupla = store.alocacoes.some((a: Alocacao) =>
    a.sala_id === novaSalaId.value && a.dia_semana === alocacao.value?.dia_semana && a.turno === alocacao.value?.turno && a.id !== props.alocacaoId
  );
  if (dupla) r.push({ id: 'p3', gravidade: 'critico', descricao: `Sala já alocada no mesmo dia/turno.` });
  return r;
});

const exigeJustificativa = computed(() => conflitosPrevistos.value.some(c => c.gravidade === 'critico'));

function salvar() {
  const res = store.editarAlocacao(
    props.alocacaoId, novaSalaId.value,
    auth.user?.username ?? 'Gestor',
    justificativa.value.trim() || undefined,
  );
  if (res.ok) { toast.success(res.mensagem); emit('salvo'); }
  else toast.error(res.mensagem);
}
</script>
