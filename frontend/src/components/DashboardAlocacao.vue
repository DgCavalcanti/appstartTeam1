<template>
  <div class="dashboard-alocacao">
    <header>
      <h1>🎯 Dashboard de Alocação Automática</h1>
    </header>

    <div class="container">
      <!-- Seção: Executar Alocação -->
      <section class="secao-execucao">
        <h2>Executar Alocação Automática</h2>
        <form @submit.prevent="executar" class="formulario-alocacao">
          <div class="form-group">
            <label for="dia">Dia da Semana:</label>
            <select v-model="diaSelecionado" id="dia" required>
              <option value="">Selecione um dia</option>
              <option value="segunda">Segunda</option>
              <option value="terca">Terça</option>
              <option value="quarta">Quarta</option>
              <option value="quinta">Quinta</option>
              <option value="sexta">Sexta</option>
            </select>
          </div>

          <div class="form-group">
            <label for="turno">Turno:</label>
            <select v-model="turnoSelecionado" id="turno" required>
              <option value="">Selecione um turno</option>
              <option value="manha">Manhã</option>
              <option value="tarde">Tarde</option>
            </select>
          </div>

          <button
            type="submit"
            :disabled="!diaSelecionado || !turnoSelecionado || carregando"
            class="botao-executar"
          >
            {{ carregando ? '⏳ Processando...' : '▶ Executar Alocação' }}
          </button>
        </form>
      </section>

      <!-- Mensagem de erro -->
      <div v-if="erro" class="alerta erro">
        <strong>❌ Erro:</strong> {{ erro }}
      </div>

      <!-- Resultado -->
      <template v-if="resultado">
        <!-- Resumo -->
        <section class="secao-resultado">
          <h2>📊 Resultado da Alocação</h2>
          <div class="resumo">
            <div class="card-metrica">
              <div class="valor">{{ resultado.alocacoes_criadas.length }}</div>
              <div class="label">Alocações Criadas</div>
            </div>
            <div class="card-metrica">
              <div class="valor">{{ resultado.grades_nao_alocadas.length }}</div>
              <div class="label">Grades Não Alocadas</div>
            </div>
            <div class="card-metrica">
              <div class="valor">{{ resultado.conflitos_detectados.length }}</div>
              <div class="label">Conflitos Detectados</div>
            </div>
          </div>
          <p v-if="resultado.resumo" class="resumo-texto">{{ resultado.resumo }}</p>
        </section>

        <!-- Tabela: Alocações Criadas -->
        <section v-if="resultado.alocacoes_criadas.length" class="secao-tabela">
          <h3>✅ Alocações Criadas</h3>
          <table class="tabela">
            <thead>
              <tr>
                <th>Grade ID</th>
                <th>Sala ID</th>
                <th>Especialidade</th>
                <th>Profissional</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="aloc in resultado.alocacoes_criadas" :key="aloc.id">
                <td>{{ aloc.grade_id }}</td>
                <td>{{ aloc.sala_id }}</td>
                <td>{{ getGradeInfo(aloc.grade_id)?.especialidade || '-' }}</td>
                <td>{{ getGradeInfo(aloc.grade_id)?.profissional || '-' }}</td>
                <td><span class="badge-sucesso">Alocada</span></td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- Tabela: Grades Não Alocadas -->
        <section v-if="resultado.grades_nao_alocadas.length" class="secao-tabela">
          <h3>⚠️ Grades Não Alocadas</h3>
          <table class="tabela">
            <thead>
              <tr>
                <th>Especialidade</th>
                <th>Profissional</th>
                <th>Dia</th>
                <th>Turno</th>
                <th>Salas Necessárias</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="grade in resultado.grades_nao_alocadas" :key="grade.id">
                <td>{{ grade.especialidade }}</td>
                <td>{{ grade.profissional }}</td>
                <td>{{ grade.dia_semana }}</td>
                <td>{{ grade.turno }}</td>
                <td>{{ grade.qtd_salas_necessarias }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- Lista: Conflitos Detectados -->
        <section v-if="resultado.conflitos_detectados.length" class="secao-conflitos">
          <h3>🔴 Conflitos Detectados</h3>
          <div class="conflitos-lista">
            <div
              v-for="conflito in resultado.conflitos_detectados"
              :key="conflito.id"
              class="conflito-card"
              :class="`gravidade-${conflito.gravidade}`"
            >
              <div class="conflito-tipo">
                <strong>{{ conflito.tipo }}</strong>
                <span class="badge" :class="`badge-${conflito.gravidade}`">
                  {{ conflito.gravidade.toUpperCase() }}
                </span>
              </div>
              <p>{{ conflito.descricao }}</p>
            </div>
          </div>
        </section>

        <!-- Botão: Salvar -->
        <div class="acoes-resultado">
          <button @click="salvarAlocacoes" class="botao-salvar">
            💾 Salvar Alocações
          </button>
          <button @click="limparResultado" class="botao-limpar">
            🔄 Limpar
          </button>
        </div>
      </template>

      <!-- Indicadores do Dashboard -->
      <section class="secao-indicadores">
        <h2>📈 Indicadores Gerais</h2>
        <div class="grid-indicadores">
          <div class="indicador">
            <div class="icone">🏢</div>
            <div class="stats">
              <div class="valor">{{ store.indicadores.totalSalas }}</div>
              <div class="label">Salas Totais</div>
            </div>
          </div>
          <div class="indicador">
            <div class="icone">✅</div>
            <div class="stats">
              <div class="valor">{{ store.indicadores.salasDisponiveis }}</div>
              <div class="label">Disponíveis</div>
            </div>
          </div>
          <div class="indicador">
            <div class="icone">🚫</div>
            <div class="stats">
              <div class="valor">{{ store.indicadores.salasBloqueadas }}</div>
              <div class="label">Bloqueadas</div>
            </div>
          </div>
          <div class="indicador">
            <div class="icone">🔴</div>
            <div class="stats">
              <div class="valor">{{ store.indicadores.conflitosCriticos }}</div>
              <div class="label">Conflitos Críticos</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useSaaStore } from '@/stores/saa';
import { useAuthStore } from '@/stores/auth';
import type { ResultadoAlocacaoAutomatica, Grade } from '@/stores/saa';

const store = useSaaStore();
const authStore = useAuthStore();

const diaSelecionado = ref('');
const turnoSelecionado = ref('');
const carregando = ref(false);
const erro = ref('');
const resultado = ref<ResultadoAlocacaoAutomatica | null>(null);

const token = computed(() => {
  return authStore.accessToken || '';
});

function getGradeInfo(gradeId: string) {
  return store.getGrade(gradeId);
}

async function executar() {
  if (!diaSelecionado.value || !turnoSelecionado.value) {
    erro.value = 'Selecione dia e turno';
    return;
  }

  if (!token.value) {
    erro.value = 'Token de autenticação não encontrado';
    return;
  }

  carregando.value = true;
  erro.value = '';
  resultado.value = null;

  const res = await store.executarAlocacaoAutomatica(
    diaSelecionado.value,
    turnoSelecionado.value,
    token.value
  );

  carregando.value = false;

  if (res.ok && res.resultado) {
    resultado.value = res.resultado;
  } else {
    erro.value = res.erro || 'Erro ao executar alocação automática';
  }
}

function salvarAlocacoes() {
  // Aqui você pode adicionar lógica para persistir as alocações
  // Por enquanto, as alocações já estão sincronizadas no store
  alert('✅ Alocações sincronizadas com sucesso!');
}

function limparResultado() {
  resultado.value = null;
  erro.value = '';
  diaSelecionado.value = '';
  turnoSelecionado.value = '';
}
</script>

<style scoped>
.dashboard-alocacao {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
  padding: 20px;
}

header {
  text-align: center;
  color: white;
  margin-bottom: 30px;
}

header h1 {
  font-size: 2.5rem;
  margin: 0;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
}

.container {
  max-width: 1200px;
  margin: 0 auto;
}

section {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

section h2 {
  color: #333;
  margin-top: 0;
  border-bottom: 2px solid #667eea;
  padding-bottom: 12px;
}

section h3 {
  color: #555;
  margin-top: 0;
}

/* Formulário */
.formulario-alocacao {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 16px;
  align-items: end;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group label {
  font-weight: 600;
  margin-bottom: 6px;
  color: #555;
}

.form-group select {
  padding: 10px;
  border: 2px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.form-group select:focus {
  outline: none;
  border-color: #667eea;
}

.botao-executar {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  white-space: nowrap;
}

.botao-executar:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.botao-executar:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Alertas */
.alerta {
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 20px;
  font-weight: 500;
}

.alerta.erro {
  background: #fee;
  color: #c33;
  border-left: 4px solid #c33;
}

/* Resultado */
.resumo {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.card-metrica {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
}

.card-metrica .valor {
  font-size: 2rem;
  font-weight: bold;
}

.card-metrica .label {
  font-size: 0.9rem;
  opacity: 0.9;
  margin-top: 8px;
}

.resumo-texto {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 6px;
  font-size: 0.95rem;
  color: #666;
}

/* Tabelas */
.secao-tabela {
  overflow-x: auto;
}

.tabela {
  width: 100%;
  border-collapse: collapse;
  margin-top: 12px;
}

.tabela thead {
  background: #f5f5f5;
}

.tabela th {
  padding: 12px;
  text-align: left;
  font-weight: 600;
  color: #555;
  border-bottom: 2px solid #ddd;
}

.tabela td {
  padding: 12px;
  border-bottom: 1px solid #eee;
}

.tabela tbody tr:hover {
  background: #f9f9f9;
}

.badge-sucesso {
  background: #d4edda;
  color: #155724;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
}

/* Conflitos */
.secao-conflitos {
  background: #fff;
}

.conflitos-lista {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  margin-top: 12px;
}

.conflito-card {
  border-left: 4px solid;
  padding: 16px;
  border-radius: 6px;
  background: #fafafa;
}

.conflito-card.gravidade-critico {
  border-left-color: #c33;
  background: #fee;
}

.conflito-card.gravidade-operacional {
  border-left-color: #ff9800;
  background: #fff3e0;
}

.conflito-card.gravidade-info {
  border-left-color: #2196f3;
  background: #e3f2fd;
}

.conflito-tipo {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.conflito-tipo strong {
  color: #333;
}

.badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
}

.badge-critico {
  background: #c33;
  color: white;
}

.badge-operacional {
  background: #ff9800;
  color: white;
}

.badge-info {
  background: #2196f3;
  color: white;
}

.conflito-card p {
  margin: 0;
  font-size: 0.9rem;
  color: #555;
  line-height: 1.4;
}

/* Ações */
.acoes-resultado {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 20px;
}

.botao-salvar,
.botao-limpar {
  padding: 12px 24px;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.botao-salvar {
  background: linear-gradient(135deg, #4caf50, #45a049);
  color: white;
}

.botao-salvar:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(76, 175, 80, 0.4);
}

.botao-limpar {
  background: #ddd;
  color: #333;
}

.botao-limpar:hover {
  background: #ccc;
}

/* Indicadores */
.grid-indicadores {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-top: 16px;
}

.indicador {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #f5f7fa, #c3cfe2);
  padding: 20px;
  border-radius: 8px;
}

.indicador .icone {
  font-size: 2.5rem;
}

.indicador .stats {
  flex: 1;
}

.indicador .valor {
  font-size: 1.8rem;
  font-weight: bold;
  color: #333;
}

.indicador .label {
  font-size: 0.9rem;
  color: #666;
  margin-top: 4px;
}

@media (max-width: 768px) {
  .formulario-alocacao {
    grid-template-columns: 1fr;
  }

  header h1 {
    font-size: 1.8rem;
  }

  .conflitos-lista {
    grid-template-columns: 1fr;
  }

  .acoes-resultado {
    flex-direction: column;
  }
}
</style>
