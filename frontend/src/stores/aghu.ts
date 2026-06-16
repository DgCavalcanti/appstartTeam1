/**
 * AGHU Store — consome os endpoints /api/aghu/* e /api/importacao/aghu/*
 *
 * Nunca carrega todas as consultas brutas no estado — usa paginação e agregados.
 */

import { defineStore } from 'pinia';
import { ref } from 'vue';
import api from '../services/api';

// ── Tipos ──────────────────────────────────────────────────────────────────

export interface GradeAghu {
  grade_id: string;
  profissional: string;
  unidade_funcional: string;
  condicao_atendimento: string;
  especialidade: string;
  situacao_grade: string;
  dia_semana: string;
  hora_inicio: string | null;
  turno: string;
  situacao_horario: string;
  quantidade_vagas: number;
  qtd_salas_necessarias: number;
}

export interface Consulta {
  consulta_id: string | null;
  grade_id: string | null;
  profissional: string | null;
  unidade_funcional: string | null;
  especialidade: string | null;
  sigla_especialidade: string | null;
  data_hora_consulta: string | null;
  dia_semana: string | null;
  turno: string | null;
  situacao_consulta: string | null;
  condicao_atendimento: string | null;
  retorno: boolean | null;
  consulta_excedente: boolean | null;
  paciente_presente: boolean | null;
}

export interface CapacidadeResumo {
  total_grades: number;
  total_grades_ativas: number;
  total_horarios_ativos: number;
  total_consultas: number;
  consultas_marcadas: number;
  vagas_livres: number;
  bloqueios: number;
  consultas_excedentes: number;
  taxa_ocupacao: number;
  taxa_excedente: number;
}

export interface ResumoEspecialidade {
  especialidade: string;
  total_consultas: number;
  marcadas: number;
  livres: number;
  bloqueios: number;
  excedentes: number;
  taxa_ocupacao: number;
  taxa_excedente: number;
}

export interface ResumoDiaTurno {
  dia_semana: string;
  turno: string;
  consultas_marcadas: number;
  vagas_livres: number;
  bloqueios: number;
  excedentes: number;
}

export interface ProblemaQualidade {
  categoria: string;
  descricao: string;
  quantidade: number;
  gravidade: 'aviso' | 'atencao' | 'critico';
}

export interface QualidadeDados {
  problemas: ProblemaQualidade[];
  total_problemas: number;
  criticos: number;
}

export interface ImportacaoResultado {
  arquivo: string;
  linhas_lidas: number;
  linhas_validas: number;
  registros_unicos: number;
  avisos: string[];
}

export interface FiltrosConsulta {
  especialidade?: string;
  unidade_funcional?: string;
  profissional?: string;
  turno?: string;
  dia_semana?: string;
  situacao_consulta?: string;
  apenas_excedentes?: boolean;
  limit?: number;
  offset?: number;
}

// ── Store ──────────────────────────────────────────────────────────────────

export const useAghuStore = defineStore('aghu', () => {

  const capacidade          = ref<CapacidadeResumo | null>(null);
  const porEspecialidade    = ref<ResumoEspecialidade[]>([]);
  const porDiaTurno         = ref<ResumoDiaTurno[]>([]);
  const qualidade           = ref<QualidadeDados | null>(null);
  const consultas           = ref<Consulta[]>([]);
  const grades              = ref<GradeAghu[]>([]);
  const carregando          = ref(false);
  const erro                = ref<string | null>(null);

  async function buscarCapacidade() {
    carregando.value = true;
    erro.value = null;
    try {
      const { data } = await api.get<CapacidadeResumo>('/api/aghu/capacidade/resumo');
      capacidade.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar resumo de capacidade.';
    } finally {
      carregando.value = false;
    }
  }

  async function buscarPorEspecialidade() {
    carregando.value = true;
    erro.value = null;
    try {
      const { data } = await api.get<ResumoEspecialidade[]>('/api/aghu/consultas/por-especialidade');
      porEspecialidade.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar por especialidade.';
    } finally {
      carregando.value = false;
    }
  }

  async function buscarPorDiaTurno() {
    carregando.value = true;
    erro.value = null;
    try {
      const { data } = await api.get<ResumoDiaTurno[]>('/api/aghu/consultas/por-dia-turno');
      porDiaTurno.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar por dia/turno.';
    } finally {
      carregando.value = false;
    }
  }

  async function buscarQualidade() {
    carregando.value = true;
    erro.value = null;
    try {
      const { data } = await api.get<QualidadeDados>('/api/aghu/qualidade-dados');
      qualidade.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar qualidade dos dados.';
    } finally {
      carregando.value = false;
    }
  }

  async function buscarConsultas(filtros: FiltrosConsulta = {}) {
    carregando.value = true;
    erro.value = null;
    try {
      const params = Object.fromEntries(
        Object.entries(filtros).filter(([, v]) => v != null && v !== '')
      );
      const { data } = await api.get<Consulta[]>('/api/aghu/consultas', { params });
      consultas.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar consultas.';
    } finally {
      carregando.value = false;
    }
  }

  async function buscarGrades(filtros: Partial<Pick<GradeAghu, 'especialidade' | 'turno' | 'dia_semana'>> = {}) {
    carregando.value = true;
    erro.value = null;
    try {
      const params = Object.fromEntries(Object.entries(filtros).filter(([, v]) => v));
      const { data } = await api.get<GradeAghu[]>('/api/aghu/grades', { params });
      grades.value = data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao buscar grades AGHU.';
    } finally {
      carregando.value = false;
    }
  }

  async function importarGradesAghu(arquivo: File): Promise<ImportacaoResultado | null> {
    carregando.value = true;
    erro.value = null;
    try {
      const form = new FormData();
      form.append('arquivo', arquivo);
      const { data } = await api.post<ImportacaoResultado>('/api/importacao/aghu/grades', form);
      await buscarCapacidade();
      return data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao importar grades.';
      return null;
    } finally {
      carregando.value = false;
    }
  }

  async function importarConsultasAghu(arquivo: File): Promise<ImportacaoResultado | null> {
    carregando.value = true;
    erro.value = null;
    try {
      const form = new FormData();
      form.append('arquivo', arquivo);
      const { data } = await api.post<ImportacaoResultado>('/api/importacao/aghu/consultas', form);
      await buscarCapacidade();
      return data;
    } catch (e: any) {
      erro.value = e?.response?.data?.detail ?? 'Erro ao importar consultas.';
      return null;
    } finally {
      carregando.value = false;
    }
  }

  return {
    capacidade, porEspecialidade, porDiaTurno, qualidade, consultas, grades,
    carregando, erro,
    buscarCapacidade, buscarPorEspecialidade, buscarPorDiaTurno,
    buscarQualidade, buscarConsultas, buscarGrades,
    importarGradesAghu, importarConsultasAghu,
  };
});
