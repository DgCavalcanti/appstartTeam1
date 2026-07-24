<template>
  <div>
    <div v-if="rotulo || mostrarValor" class="flex items-baseline justify-between mb-1">
      <span v-if="rotulo" class="text-xs text-gray-500">{{ rotulo }}</span>
      <span v-if="mostrarValor" class="text-xs tabular-nums font-medium text-paper-text">
        {{ Math.round(pct) }}%
      </span>
    </div>
    <div class="h-2 rounded-full bg-gray-100 overflow-hidden">
      <div
        class="h-full rounded-full transition-all"
        :class="cor"
        :style="{ width: Math.min(100, Math.max(0, pct)) + '%' }"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    pct: number;
    rotulo?: string;
    mostrarValor?: boolean;
  }>(),
  { rotulo: '', mostrarValor: true }
);

/**
 * A cor comunica o nível de ocupação sem precisar de legenda: verde folgado,
 * âmbar apertando, vermelho no limite. Acima de 100% (só sob obrigatoriedade)
 * segue vermelho.
 */
const cor = computed(() => {
  if (props.pct >= 95) return 'bg-paper-danger';
  if (props.pct >= 80) return 'bg-paper-warning';
  if (props.pct >= 50) return 'bg-paper-success';
  return 'bg-paper-info';
});
</script>
