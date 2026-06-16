/**
 * SAA Store — Sistema de Apoio à Alocação
 *
 * Consome a API backend em vez de processar CSVs no navegador.
 * A lógica de conflitos reside exclusivamente no backend.
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import api from '../services/api';
import type { ImportacaoResultado } from './aghu';

// ─── Tipos (contrato MVP — IDs como string) ───────────────────────────────────

export interface Sala {
  id: string;
  numero: string;
  bloco: string;
  andar: string;
  status: 'disponivel' | 'bloqueada' | 'reforma' | 'manutencao' | 'ocupada';
  acessibilidade: boolean;
  equipamentos: string[];
  especialidade_preferencial: string | null;
}

export interface Grade {
  id: string;
  especialidade: string;
  profissional: string;
  dia_semana: string;
  turno: 'Manhã' | 'Tarde' | 'Noite' | string;
  qtd_salas_necessarias: number;
}

export interface Alocacao {
  id: string;
  grade_id: string;
  sala_id: string;
  dia_semana: string;
  turno: string;
}

export interface Restricao {
  id: string;
  sala_id: string;
  tipo: string;
  valor: string;
}

export type GravidadeConflito = 'critico' | 'operacional' | 'info';

export interface Conflito {
  id: string;
  tipo: string;
  gravidade: GravidadeConflito;
  descricao: string;
  sala_id?: string;
  grade_id?: string;
  alocacao_id?: string;
  especialidade?: string;
  dia_semana?: string;
  turno?: string;
}

export interface HistoricoAjuste {
  id: string;
  alocacao_id: string;
  sala_anterior_id: string;
  sala_nova_id: string;
  data_hora: string;
  usuario: string;
  conflitos_antes: Conflito[];
  conflitos_depois: Conflito[];
  justificativa?: string;
}

export interface DashboardResumo {
  total_salas: number;
  salas_disponiveis: number;
  salas_bloqueadas: number;
  salas_reforma: number;
  total_conflitos: number;
  conflitos_criticos: number;
  total_grades: number;
  total_alocacoes: number;
}

export interface AjusteAlocacaoRequest {
  alocacao_id: string;
  nova_sala_id: string;
  justificativa?: string;
}

export interface AjusteAlocacaoResponse {
  alocacao: Alocacao;
  conflitos_depois: Conflito[];
  historico: HistoricoAjuste;
}

// ─── Store ────────────────────────────────────────────────────────────────────

export const useSaaStore = defineStore('saa', () => {

  // Estado
  const salas      = ref<Sala[]>([]);
  const grades     = ref<Grade[]>([]);
  const alocacoes  = ref<Alocacao[]>([]);
  const restricoes = ref<Restricao[]>([]);
  const conflitos  = ref<Conflito[]>([]);
  const historico  = ref<HistoricoAjuste[]>([]);
  const resumo     = ref<DashboardResumo | null>(null);

  // Loading / erro
  const carregando = ref(false);
  const erro       = ref<string | null>(null);

  // ── Computed ──────────────────────────────────────────────────────────────
  const indicadores = computed(() => ({
    totalSalas:        resumo.value?.total_salas          ?? salas.value.length,
    salasDisponiveis:  resumo.value?.salas_disponiveis    ?? salas.value.filter((s: Sala) => s.status === 'disponivel').length,
    salasBloqueadas:   resumo.value?.salas_bloqueadas     ?? salas.value.filter((s: Sala) => s.status === 'bloqueada').length,
    salasReforma:      resumo.value?.salas_reforma        ?? salas.value.filter((s: Sala) => s.status === 'reforma' || s.status === 'manutencao').length,
    totalConflitos:    resumo.value?.total_conflitos      ?? conflitos.value.length,
    conflitosCriticos: resumo.value?.conflitos_criticos   ?? conflitos.value.filter((c: Conflito) => c.gravidade === 'critico').length,
  }));

  // ── Ações de busca (API) ───────────────────────────────────────────────────

  async function buscarGrades(filtros?: { especialidade?: string; dia_semana?: string; turno?: string }) {
    carregando.value = true;
    erro.value = null;
    try {
      const params = filtros ? Object.fromEntries(Object.entries(filtros).filter(([, v]) => v != null)) : {};
      const { data } = await api.get<Grade[]>('/api/grades', { params });
      grades.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar grades.';
    } finally {
      carregando.value = false;
    }
  }

  async function buscarSalas(filtros?: { bloco?: string; status?: string; especialidade?: string }) {
    carregando.value = true;
    erro.value = null;
    try {
      const params = filtros ? Object.fromEntries(Object.entries(filtros).filter(([, v]) => v != null)) : {};
      const { data } = await api.get<Sala[]>('/api/salas', { params });
      salas.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar salas.';
    } finally {
      carregando.value = false;
    }
  }

  async function buscarRestricoes() {
    carregando.value = true;
    erro.value = null;
    try {
      const { data } = await api.get<Restricao[]>('/api/restricoes');
      restricoes.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar restrições.';
    } finally {
      carregando.value = false;
    }
  }

  async function buscarAlocacoes(filtros?: { dia_semana?: string; turno?: string }) {
    carregando.value = true;
    erro.value = null;
    try {
      const params = filtros ? Object.fromEntries(Object.entries(filtros).filter(([, v]) => v != null)) : {};
      const { data } = await api.get<Alocacao[]>('/api/alocacoes', { params });
      alocacoes.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar alocações.';
    } finally {
      carregando.value = false;
    }
  }

  async function buscarResumoDashboard() {
    carregando.value = true;
    erro.value = null;
    try {
      const { data } = await api.get<DashboardResumo>('/api/dashboard/resumo');
      resumo.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar resumo.';
    } finally {
      carregando.value = false;
    }
  }

  async function buscarConflitos(filtros?: { dia_semana?: string; turno?: string; especialidade?: string }) {
    carregando.value = true;
    erro.value = null;
    try {
      const params = filtros ? Object.fromEntries(Object.entries(filtros).filter(([, v]) => v != null)) : {};
      const { data } = await api.get<Conflito[]>('/api/dashboard/conflitos', { params });
      conflitos.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar conflitos.';
    } finally {
      carregando.value = false;
    }
  }

  async function ajustarAlocacao(req: AjusteAlocacaoRequest): Promise<AjusteAlocacaoResponse | null> {
    carregando.value = true;
    erro.value = null;
    try {
      const { data } = await api.post<AjusteAlocacaoResponse>('/api/alocacoes/ajustar', req);
      // Atualiza alocação localmente para reatividade imediata
      const idx = alocacoes.value.findIndex((a: Alocacao) => a.id === data.alocacao.id);
      if (idx !== -1) alocacoes.value[idx] = data.alocacao;
      conflitos.value = data.conflitos_depois;
      historico.value.unshift(data.historico);
      return data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao ajustar alocação.';
      return null;
    } finally {
      carregando.value = false;
    }
  }

  async function buscarHistorico() {
    carregando.value = true;
    erro.value = null;
    try {
      const { data } = await api.get<HistoricoAjuste[]>('/api/alocacoes/historico');
      historico.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar histórico.';
    } finally {
      carregando.value = false;
    }
  }

  // ── Importação (upload real via multipart, persiste no backend) ─────────

  async function importarSalas(arquivo: File): Promise<ImportacaoResultado | null> {
    carregando.value = true;
    erro.value = null;
    try {
      const form = new FormData();
      form.append('arquivo', arquivo);
      // Content-Type: undefined remove o header JSON padrão da instância
      // `api`, deixando o navegador definir o boundary do multipart.
      const { data } = await api.post<ImportacaoResultado>('/api/importacao/salas', form, {
        headers: { 'Content-Type': undefined } as any,
      });
      await buscarSalas();
      return data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao importar salas.';
      return null;
    } finally {
      carregando.value = false;
    }
  }

  async function importarRestricoes(arquivo: File): Promise<ImportacaoResultado | null> {
    carregando.value = true;
    erro.value = null;
    try {
      const form = new FormData();
      form.append('arquivo', arquivo);
      const { data } = await api.post<ImportacaoResultado>('/api/importacao/restricoes', form, {
        headers: { 'Content-Type': undefined } as any,
      });
      await buscarRestricoes();
      return data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao importar restrições.';
      return null;
    } finally {
      carregando.value = false;
    }
  }

  async function importarAlocacoes(arquivo: File): Promise<ImportacaoResultado | null> {
    carregando.value = true;
    erro.value = null;
    try {
      const form = new FormData();
      form.append('arquivo', arquivo);
      const { data } = await api.post<ImportacaoResultado>('/api/importacao/alocacoes', form, {
        headers: { 'Content-Type': undefined } as any,
      });
      await buscarAlocacoes();
      return data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao importar alocações.';
      return null;
    } finally {
      carregando.value = false;
    }
  }

  // ── Helpers de busca local (fallback após dados carregados) ───────────────

  function getSala(id: string)  { return salas.value.find((s: Sala) => s.id === id); }
  function getGrade(id: string) { return grades.value.find((g: Grade) => g.id === id); }

  function getConflitosParaSala(salaId: string) {
    return conflitos.value.filter((c: Conflito) => c.sala_id === salaId);
  }

  function getConflitosParaGrade(gradeId: string) {
    return conflitos.value.filter((c: Conflito) => c.grade_id === gradeId);
  }

  function getAlocacaoPorGrade(gradeId: string) {
    return alocacoes.value.find((a: Alocacao) => a.grade_id === gradeId);
  }

  return {
    // Estado
    salas, grades, alocacoes, restricoes, conflitos, historico, resumo,
    carregando, erro,
    // Computeds
    indicadores,
    // Ações de API
    buscarGrades, buscarSalas, buscarRestricoes, buscarAlocacoes,
    buscarResumoDashboard, buscarConflitos, ajustarAlocacao, buscarHistorico,
    // Importação (upload real)
    importarSalas, importarAlocacoes, importarRestricoes,
    // Helpers
    getSala, getGrade, getConflitosParaSala, getConflitosParaGrade, getAlocacaoPorGrade,
  };
});
