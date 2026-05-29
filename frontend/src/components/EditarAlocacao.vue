<template>
  <div>
    <!-- Alocação atual -->
    <div class="mb-4 p-3 bg-gray-50 rounded text-sm">
      <p class="text-gray-500 mb-1">Grade</p>
      <p class="font-medium">{{ grade.especialidade }} — {{ grade.profissional }}</p>
      <p class="text-gray-500">{{ grade.dia_semana }} / {{ grade.turno }}</p>
    </div>

    <div class="mb-4 p-3 bg-gray-50 rounded text-sm" v-if="alocacaoAtual">
      <p class="text-gray-500 mb-1">Sala atual</p>
      <p class="font-bold text-lg">{{ store.getSala(alocacaoAtual.sala_id)?.numero ?? alocacaoAtual.sala_id }}</p>
      <p class="text-gray-500">Bloco {{ store.getSala(alocacaoAtual.sala_id)?.bloco ?? '?' }}</p>
    </div>
    <div v-else class="mb-4 p-3 bg-red-50 rounded text-sm text-red-700">
      Esta grade não possui sala alocada.
    </div>

    <!-- Seleção de nova sala -->
    <div class="form-group">
      <label class="form-label">Selecionar nova sala</label>
      <select v-model="novaSalaId" class="form-control">
        <option value="">— Selecione —</option>
        <option v-for="sala in salasDisponiveis" :key="sala.id" :value="sala.id">
          Sala {{ sala.numero }} (Bloco {{ sala.bloco }}) — {{ sala.status }} — {{ sala.especialidade_preferencial }}
        </option>
      </select>
    </div>

    <!-- Pré-visualização de conflitos após a mudança -->
    <div v-if="novaSalaId && conflitosPrevistos.length > 0" class="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded text-sm">
      <p class="font-semibold text-yellow-800 mb-2 flex items-center gap-1">
        <ExclamationTriangleIcon class="h-4 w-4" />
        {{ conflitosPrevistos.length }} alerta(s) detectado(s)
      </p>
      <ul class="space-y-1">
        <li v-for="c in conflitosPrevistos" :key="c.id" class="text-yellow-700">
          <span class="font-bold uppercase text-xs">{{ c.gravidade }}:</span> {{ c.descricao }}
        </li>
      </ul>
    </div>

    <!-- Justificativa (obrigatória se houver conflito crítico) -->
    <div v-if="exigeJustificativa" class="form-group">
      <label class="form-label text-red-700">
        Justificativa obrigatória (há conflito crítico)
      </label>
      <textarea v-model="justificativa" class="form-control" rows="3"
        placeholder="Descreva o motivo de prosseguir com esta alocação..." />
    </div>
    <div v-else-if="novaSalaId && conflitosPrevistos.length > 0" class="form-group">
      <label class="form-label">Justificativa (recomendada)</label>
      <textarea v-model="justificativa" class="form-control" rows="2"
        placeholder="Descreva o motivo..." />
    </div>

    <!-- Ações -->
    <div class="flex justify-end gap-3 mt-4">
      <Button variant="default" @click="$emit('cancelar')">Cancelar</Button>
      <Button
        variant="primary"
        :disabled="!novaSalaId || (exigeJustificativa && !justificativa.trim())"
        @click="salvar"
      >Confirmar Alteração</Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ExclamationTriangleIcon } from '@heroicons/vue/24/outline';
import { useSaaStore, type Grade, type Alocacao } from '../stores/saa';
import { useAuthStore } from '../stores/auth';
import { useToast } from 'vue-toastification';
import Button from './Button.vue';

const props = defineProps<{ grade: Grade }>();
const emit  = defineEmits(['salvo', 'cancelar']);

const store    = useSaaStore();
const auth     = useAuthStore();
const toast    = useToast();

const novaSalaId    = ref('');
const justificativa = ref('');

const alocacaoAtual = computed(() => store.getAlocacaoPorGrade(props.grade.id));

// Salas disponíveis (exclui bloqueadas e em reforma do MVP, mas as lista com aviso)
const salasDisponiveis = computed(() => store.salas);

/**
 * Simula conflitos que existiriam se a nova sala fosse selecionada.
 * Cruza a nova sala com as regras do motor de conflitos para pré-visualização.
 */
const conflitosPrevistos = computed(() => {
  if (!novaSalaId.value) return [];
  const sala = store.getSala(novaSalaId.value);
  if (!sala) return [];
  const resultado = [];

  if (sala.status === 'bloqueada' || sala.status === 'reforma' || sala.status === 'manutencao') {
    resultado.push({ id: 'prev-1', gravidade: 'critico', descricao: `Sala ${sala.numero} está ${sala.status}.` });
  }
  if (sala.especialidade_preferencial && sala.especialidade_preferencial !== props.grade.especialidade && sala.especialidade_preferencial !== 'Geral') {
    resultado.push({ id: 'prev-2', gravidade: 'operacional', descricao: `Sala preferencial para ${sala.especialidade_preferencial}, mas grade é de ${props.grade.especialidade}.` });
  }
  // Conflito de dupla alocação no mesmo dia/turno
  const jaOcupada = store.alocacoes.some((a: Alocacao) =>
    a.sala_id    === novaSalaId.value &&
    a.dia_semana === props.grade.dia_semana &&
    a.turno      === props.grade.turno &&
    a.grade_id   !== props.grade.id
  );
  if (jaOcupada) {
    resultado.push({ id: 'prev-3', gravidade: 'critico', descricao: `Sala ${sala.numero} já possui outra grade no mesmo dia/turno.` });
  }
  return resultado;
});

const exigeJustificativa = computed(() =>
  conflitosPrevistos.value.some(c => c.gravidade === 'critico')
);

function salvar() {
  if (!novaSalaId.value) return;
  if (exigeJustificativa.value && !justificativa.value.trim()) {
    toast.error('Justificativa obrigatória para conflitos críticos.');
    return;
  }

  // Se não há alocação ainda, cria uma nova
  if (!alocacaoAtual.value) {
    store.alocacoes.push({
      id:         `A-${Date.now()}`,
      grade_id:   props.grade.id,
      sala_id:    novaSalaId.value,
      dia_semana: props.grade.dia_semana,
      turno:      props.grade.turno,
    });
    toast.success('Alocação criada com sucesso.');
    emit('salvo');
    return;
  }

  const resultado = store.editarAlocacao(
    alocacaoAtual.value.id,
    novaSalaId.value,
    auth.user?.username ?? 'Gestor',
    justificativa.value.trim() || undefined,
  );

  if (resultado.ok) {
    toast.success(resultado.mensagem);
    emit('salvo');
  } else {
    toast.error(resultado.mensagem);
  }
}
</script>
