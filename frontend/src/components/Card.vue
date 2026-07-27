<template>
  <div class="bg-white shadow-paper rounded-lg transition-shadow duration-300 hover:shadow-md">
    <div v-if="$slots.header" class="p-4 border-b border-gray-100">
      <slot name="header"></slot>
    </div>
    <div class="p-6">
      <slot></slot>
    </div>
    <div v-if="$slots.footer" class="p-4 border-t border-gray-100">
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>
