<template>
  <button
    :class="[buttonClass, { 'cursor-not-allowed': loading }]"
    :disabled="loading || disabled"
    class="flex items-center justify-center font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline transition-all duration-300 ease-in-out shadow-sm active:scale-95"
  >
    <svg v-if="loading" class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>

    <span v-if="$slots.icon && !loading" class="mr-2">
      <slot name="icon"></slot>
    </span>
    <slot></slot>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps({
  variant: {
    type: String,
    default: 'primary',
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const buttonClass = computed(() => {
  if (props.disabled || props.loading) {
    return 'bg-paper-disabled text-gray-500';
  }
  switch (props.variant) {
    case 'primary':
      return 'bg-paper-primary hover:bg-paper-primary-hover text-white';
    case 'info':
      return 'bg-paper-info hover:bg-paper-info-hover text-white';
    case 'success':
      return 'bg-paper-success hover:bg-paper-success-hover text-white';
    case 'warning':
      return 'bg-paper-warning hover:bg-paper-warning-hover text-white';
    case 'danger':
      return 'bg-paper-danger hover:bg-paper-danger-hover text-white';
    default:
      return 'bg-paper-default hover:bg-paper-default-hover text-white';
  }
});


</script>