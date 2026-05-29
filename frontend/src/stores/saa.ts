/**
 * SAA Store — Sistema de Apoio à Alocação
 * 
 * Store central do MVP. Gerencia estado reativo de salas, grades,
 * alocações e restrições, e expõe o motor de verificação de conflitos
 * que é recalculado automaticamente a cada mudança de dados.
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

// ─── Tipos ───────────────────────────────────────────────────────────────────

export interface Sala {
  id: string;
  numero: string;
  bloco: string;
  andar: string;
  status: 'disponivel' | 'bloqueada' | 'reforma' | 'manutencao' | 'ocupada';
  acessibilidade: boolean;
  equipamentos: string[];          // ex: ["ECG", "Ultrassom"]
  especialidade_preferencial: string;
}

export interface Grade {
  id: string;
  especialidade: string;
  profissional: string;
  dia_semana: string;             // 'Segunda', 'Terça', ...
  turno: 'Manhã' | 'Tarde' | 'Noite';
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
  tipo: string;                   // ex: 'especialidade_exclusiva', 'equipamento_obrigatorio'
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

// ─── Store ───────────────────────────────────────────────────────────────────

export const useSaaStore = defineStore('saa', () => {

  // Estado bruto importado via CSV
  const salas      = ref<Sala[]>([]);
  const grades     = ref<Grade[]>([]);
  const alocacoes  = ref<Alocacao[]>([]);
  const restricoes = ref<Restricao[]>([]);

  // Histórico de ajustes manuais (MVP: em memória)
  const historico  = ref<HistoricoAjuste[]>([]);

  // ── Computed: conflitos (recalculados reativamente) ────────────────────────
  /**
   * Motor de verificação de conflitos.
   * Executado automaticamente pelo Vue sempre que salas, grades,
   * alocações ou restrições mudarem. Cobre todos os tipos do MVP.
   */
  const conflitos = computed<Conflito[]>(() => {
    const resultado: Conflito[] = [];
    let seq = 0;
    const uid = () => `conf-${++seq}`;

    // Índices para busca O(1)
    const salaMap   = new Map(salas.value.map(s => [s.id, s]));
    const gradeMap  = new Map(grades.value.map(g => [g.id, g]));

    // ── R1: Sala em reforma/manutenção sendo usada ─────────────────────────
    for (const aloc of alocacoes.value) {
      const sala = salaMap.get(aloc.sala_id);
      if (!sala) continue;
      if (sala.status === 'reforma' || sala.status === 'manutencao') {
        resultado.push({
          id: uid(), tipo: 'sala_indisponivel', gravidade: 'critico',
          descricao: `Sala ${sala.numero} (${sala.status}) está alocada para a grade ${aloc.grade_id} em ${aloc.dia_semana}/${aloc.turno}.`,
          sala_id: sala.id, alocacao_id: aloc.id,
        });
      }
      // ── R2: Sala bloqueada associada a grade ─────────────────────────────
      if (sala.status === 'bloqueada') {
        resultado.push({
          id: uid(), tipo: 'sala_bloqueada', gravidade: 'critico',
          descricao: `Sala ${sala.numero} está bloqueada mas possui alocação em ${aloc.dia_semana}/${aloc.turno}.`,
          sala_id: sala.id, alocacao_id: aloc.id,
        });
      }
    }

    // ── R3: Mesma sala em mais de uma grade no mesmo dia/turno ─────────────
    const chaveAlocacao = new Map<string, Alocacao[]>();
    for (const aloc of alocacoes.value) {
      const chave = `${aloc.sala_id}|${aloc.dia_semana}|${aloc.turno}`;
      if (!chaveAlocacao.has(chave)) chaveAlocacao.set(chave, []);
      chaveAlocacao.get(chave)!.push(aloc);
    }
    for (const [chave, grupo] of chaveAlocacao.entries()) {
      if (grupo.length > 1) {
        const [salaId, dia, turno] = chave.split('|');
        const sala = salaMap.get(salaId);
        resultado.push({
          id: uid(), tipo: 'dupla_alocacao', gravidade: 'critico',
          descricao: `Sala ${sala?.numero ?? salaId} alocada para ${grupo.length} grades simultâneas em ${dia}/${turno}.`,
          sala_id: salaId,
        });
      }
    }

    // ── R4: Especialidade em sala sem equipamento adequado ─────────────────
    for (const aloc of alocacoes.value) {
      const sala  = salaMap.get(aloc.sala_id);
      const grade = gradeMap.get(aloc.grade_id);
      if (!sala || !grade) continue;

      // Verificar restrições de equipamento para a especialidade
      const restricoesEspecialidade = restricoes.value.filter(
        r => r.tipo === 'equipamento_obrigatorio' && r.sala_id === sala.id
      );
      for (const restricao of restricoesEspecialidade) {
        if (!sala.equipamentos.includes(restricao.valor)) {
          resultado.push({
            id: uid(), tipo: 'equipamento_ausente', gravidade: 'operacional',
            descricao: `Sala ${sala.numero} não possui "${restricao.valor}" exigido para ${grade.especialidade}.`,
            sala_id: sala.id, grade_id: grade.id,
          });
        }
      }

      // Verificar compatibilidade de especialidade preferencial
      if (
        sala.especialidade_preferencial &&
        sala.especialidade_preferencial !== grade.especialidade &&
        sala.especialidade_preferencial !== 'Geral'
      ) {
        resultado.push({
          id: uid(), tipo: 'especialidade_incompativel', gravidade: 'operacional',
          descricao: `Sala ${sala.numero} é preferencial para ${sala.especialidade_preferencial}, mas está alocada para ${grade.especialidade}.`,
          sala_id: sala.id, grade_id: grade.id,
        });
      }
    }

    // ── R5: Grade sem sala associada ───────────────────────────────────────
    const gradesAlocadas = new Set(alocacoes.value.map(a => a.grade_id));
    for (const grade of grades.value) {
      if (!gradesAlocadas.has(grade.id)) {
        resultado.push({
          id: uid(), tipo: 'grade_sem_sala', gravidade: 'critico',
          descricao: `Grade de ${grade.especialidade} (${grade.profissional}) em ${grade.dia_semana}/${grade.turno} não tem sala atribuída.`,
          grade_id: grade.id,
        });
      }
    }

    return resultado;
  });

  // ── Computed: indicadores do dashboard ────────────────────────────────────
  const indicadores = computed(() => ({
    totalSalas:         salas.value.length,
    salasDisponiveis:   salas.value.filter(s => s.status === 'disponivel').length,
    salasBloqueadas:    salas.value.filter(s => s.status === 'bloqueada').length,
    salasReforma:       salas.value.filter(s => s.status === 'reforma' || s.status === 'manutencao').length,
    totalConflitos:     conflitos.value.length,
    conflitosCriticos:  conflitos.value.filter(c => c.gravidade === 'critico').length,
  }));

  // ── Ações: importar CSVs ───────────────────────────────────────────────────

  /**
   * Parser CSV simples (primeira linha = cabeçalho).
   * Retorna array de objetos com chaves do cabeçalho.
   */
  function parseCsv(texto: string): Record<string, string>[] {
    const linhas = texto.trim().split(/\r?\n/);
    if (linhas.length < 2) return [];
    const cabecalho = linhas[0].split(',').map(c => c.trim().replace(/^"|"$/g, ''));
    return linhas.slice(1).map(linha => {
      const valores = linha.split(',').map(v => v.trim().replace(/^"|"$/g, ''));
      return Object.fromEntries(cabecalho.map((c, i) => [c, valores[i] ?? '']));
    });
  }

  /** Importa grades.csv */
  function importarGrades(csv: string): { ok: boolean; mensagem: string } {
    const registros = parseCsv(csv);
    const obrigatorias = ['id', 'especialidade', 'profissional', 'dia_semana', 'turno', 'qtd_salas_necessarias'];
    const cabecalho = Object.keys(registros[0] ?? {});
    const ausentes = obrigatorias.filter(c => !cabecalho.includes(c));
    if (ausentes.length) return { ok: false, mensagem: `Colunas ausentes: ${ausentes.join(', ')}` };

    grades.value = registros.map(r => ({
      id:                    r.id,
      especialidade:         r.especialidade,
      profissional:          r.profissional,
      dia_semana:            r.dia_semana,
      turno:                 r.turno as Grade['turno'],
      qtd_salas_necessarias: parseInt(r.qtd_salas_necessarias) || 1,
    }));
    return { ok: true, mensagem: `${grades.value.length} grades importadas.` };
  }

  /** Importa salas.csv */
  function importarSalas(csv: string): { ok: boolean; mensagem: string } {
    const registros = parseCsv(csv);
    const obrigatorias = ['id', 'numero', 'bloco', 'status'];
    const cabecalho = Object.keys(registros[0] ?? {});
    const ausentes = obrigatorias.filter(c => !cabecalho.includes(c));
    if (ausentes.length) return { ok: false, mensagem: `Colunas ausentes: ${ausentes.join(', ')}` };

    salas.value = registros.map(r => ({
      id:                      r.id,
      numero:                  r.numero,
      bloco:                   r.bloco,
      andar:                   r.andar ?? '',
      status:                  r.status as Sala['status'],
      acessibilidade:          r.acessibilidade === 'true' || r.acessibilidade === '1',
      equipamentos:            r.equipamentos ? r.equipamentos.split(';').map(e => e.trim()) : [],
      especialidade_preferencial: r.especialidade_preferencial ?? 'Geral',
    }));
    return { ok: true, mensagem: `${salas.value.length} salas importadas.` };
  }

  /** Importa alocacoes.csv */
  function importarAlocacoes(csv: string): { ok: boolean; mensagem: string } {
    const registros = parseCsv(csv);
    const obrigatorias = ['id', 'grade_id', 'sala_id', 'dia_semana', 'turno'];
    const cabecalho = Object.keys(registros[0] ?? {});
    const ausentes = obrigatorias.filter(c => !cabecalho.includes(c));
    if (ausentes.length) return { ok: false, mensagem: `Colunas ausentes: ${ausentes.join(', ')}` };

    alocacoes.value = registros.map(r => ({
      id:         r.id,
      grade_id:   r.grade_id,
      sala_id:    r.sala_id,
      dia_semana: r.dia_semana,
      turno:      r.turno,
    }));
    return { ok: true, mensagem: `${alocacoes.value.length} alocações importadas.` };
  }

  /** Importa restricoes.csv */
  function importarRestricoes(csv: string): { ok: boolean; mensagem: string } {
    const registros = parseCsv(csv);
    const obrigatorias = ['id', 'sala_id', 'tipo', 'valor'];
    const cabecalho = Object.keys(registros[0] ?? {});
    const ausentes = obrigatorias.filter(c => !cabecalho.includes(c));
    if (ausentes.length) return { ok: false, mensagem: `Colunas ausentes: ${ausentes.join(', ')}` };

    restricoes.value = registros.map(r => ({
      id:      r.id,
      sala_id: r.sala_id,
      tipo:    r.tipo,
      valor:   r.valor,
    }));
    return { ok: true, mensagem: `${restricoes.value.length} restrições importadas.` };
  }

  // ── Ação: editar alocação ──────────────────────────────────────────────────

  /**
   * Altera a sala de uma alocação.
   * Registra automaticamente no histórico antes e depois da mudança.
   * Os conflitos são recalculados reativamente pelo computed.
   * 
   * @param alocacaoId  ID da alocação a ser alterada
   * @param novaSalaId  ID da nova sala
   * @param usuario     Nome do usuário que fez a alteração
   * @param justificativa Opcional — obrigatório quando há conflitos críticos
   */
  function editarAlocacao(
    alocacaoId: string,
    novaSalaId: string,
    usuario: string,
    justificativa?: string
  ): { ok: boolean; mensagem: string } {
    const idx = alocacoes.value.findIndex(a => a.id === alocacaoId);
    if (idx === -1) return { ok: false, mensagem: 'Alocação não encontrada.' };

    const salaExiste = salas.value.some(s => s.id === novaSalaId);
    if (!salaExiste) return { ok: false, mensagem: 'Sala não encontrada.' };

    // Captura snapshot dos conflitos ANTES da alteração
    const conflitosBefore = conflitos.value.filter(
      c => c.alocacao_id === alocacaoId || c.sala_id === alocacoes.value[idx].sala_id
    );

    const salaAnteriorId = alocacoes.value[idx].sala_id;

    // Aplica a mudança — isso aciona o recálculo reativo dos conflitos
    alocacoes.value[idx] = { ...alocacoes.value[idx], sala_id: novaSalaId };

    // Captura snapshot dos conflitos DEPOIS da alteração
    const conflitosAfter = conflitos.value.filter(
      c => c.alocacao_id === alocacaoId || c.sala_id === novaSalaId
    );

    // Registra no histórico
    historico.value.unshift({
      id:              `hist-${Date.now()}`,
      alocacao_id:     alocacaoId,
      sala_anterior_id: salaAnteriorId,
      sala_nova_id:    novaSalaId,
      data_hora:       new Date().toLocaleString('pt-BR'),
      usuario,
      conflitos_antes:  conflitosBefore,
      conflitos_depois: conflitosAfter,
      justificativa,
    });

    return { ok: true, mensagem: 'Alocação atualizada. Conflitos recalculados.' };
  }

  // ── Helpers de busca ───────────────────────────────────────────────────────

  function getSala(id: string)  { return salas.value.find(s => s.id === id); }
  function getGrade(id: string) { return grades.value.find(g => g.id === id); }

  function getConflitosParaSala(salaId: string) {
    return conflitos.value.filter(c => c.sala_id === salaId);
  }

  function getConflitosParaGrade(gradeId: string) {
    return conflitos.value.filter(c => c.grade_id === gradeId);
  }

  function getAlocacaoPorGrade(gradeId: string) {
    return alocacoes.value.find(a => a.grade_id === gradeId);
  }

  return {
    // Estado
    salas, grades, alocacoes, restricoes, historico,
    // Computeds reativos
    conflitos, indicadores,
    // Importação
    importarGrades, importarSalas, importarAlocacoes, importarRestricoes,
    // Edição
    editarAlocacao,
    // Helpers
    getSala, getGrade, getConflitosParaSala, getConflitosParaGrade, getAlocacaoPorGrade,
  };
});
