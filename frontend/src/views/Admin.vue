<template>
  <Card>
    <div v-if="authStore.isAdmin">
      <h1 class="text-2xl font-bold text-green-600">Área de Administração</h1>
      <p class="mt-4">Bem-vindo, administrador! Este conteúdo é visível apenas para usuários com privilégios de administrador.</p>
      <div v-if="authStore.user" class="mt-6 p-4 bg-gray-100 rounded">
        <h3 class="font-bold">Informações do Usuário (do AD):</h3>
        <pre class="text-sm whitespace-pre-wrap">{{ JSON.stringify(authStore.user, null, 2) }}</pre>
      </div>
    </div>
    <div v-else>
      <h1 class="text-2xl font-bold text-red-600">Acesso Negado</h1>
      <p class="mt-4">Você não possui privilégios suficientes para visualizar esta página.</p>
    </div>
  </Card>
</template>

<script setup lang="ts">
import Card from '../components/Card.vue';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
</script>
