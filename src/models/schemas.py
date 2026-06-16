"""
Schemas Pydantic do SAA — contrato MVP com IDs string, compatível com o frontend Vue 3.
"""
from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class Grade(BaseModel):
    id: str
    especialidade: str
    profissional: str
    dia_semana: str
    turno: str
    qtd_salas_necessarias: int


# ── Formato real AGHU (vw_grades.csv) ────────────────────────────────────────

class GradeAghu(BaseModel):
    """Grade no formato real exportado do AGHU (vw_grades.csv)."""
    grade_id: str                          # valor original de 'Grade'
    profissional: str
    unidade_funcional: str
    condicao_atendimento: str
    especialidade: str
    situacao_grade: str
    dia_semana: str
    hora_inicio: Optional[str] = None
    turno: str
    situacao_horario: str
    quantidade_vagas: int                  # vagas/atendimentos planejados — NÃO é número de salas
    qtd_salas_necessarias: int = 1         # sempre 1 no MVP (regra de negócio)


# ── Consultas (vw_consultas_2026.csv) ─────────────────────────────────────────

class Consulta(BaseModel):
    """Registro de consulta exportado do AGHU."""
    consulta_id: Optional[str] = None
    grade_id: Optional[str] = None
    profissional: Optional[str] = None
    unidade_funcional: Optional[str] = None
    especialidade: Optional[str] = None
    sigla_especialidade: Optional[str] = None
    data_hora_consulta: Optional[str] = None
    dia_semana: Optional[str] = None
    turno: Optional[str] = None
    situacao_consulta: Optional[str] = None
    condicao_atendimento: Optional[str] = None
    retorno: Optional[bool] = None
    consulta_excedente: Optional[bool] = None
    paciente_presente: Optional[bool] = None


# ── Schemas de análise e indicadores ─────────────────────────────────────────

class CapacidadeResumo(BaseModel):
    total_grades: int
    total_grades_ativas: int
    total_horarios_ativos: int
    total_consultas: int
    consultas_marcadas: int
    vagas_livres: int
    bloqueios: int
    consultas_excedentes: int
    taxa_ocupacao: float          # marcadas / (marcadas + livres)
    taxa_excedente: float         # excedentes / total_consultas


class ResumoEspecialidade(BaseModel):
    especialidade: str
    total_consultas: int
    marcadas: int
    livres: int
    bloqueios: int
    excedentes: int
    taxa_ocupacao: float
    taxa_excedente: float


class ResumoDiaTurno(BaseModel):
    dia_semana: str
    turno: str
    consultas_marcadas: int
    vagas_livres: int
    bloqueios: int
    excedentes: int


class ProblemaQualidade(BaseModel):
    categoria: str
    descricao: str
    quantidade: int
    gravidade: str    # aviso | atencao | critico


class QualidadeDados(BaseModel):
    problemas: list[ProblemaQualidade]
    total_problemas: int
    criticos: int


class ImportacaoResultado(BaseModel):
    arquivo: str
    linhas_lidas: int
    linhas_validas: int
    registros_unicos: int
    avisos: list[str]


class Sala(BaseModel):
    id: str
    numero: str
    bloco: str
    andar: str
    status: str                              # disponivel | bloqueada | reforma | manutencao
    acessibilidade: bool
    equipamentos: list[str]
    especialidade_preferencial: Optional[str] = None


class Restricao(BaseModel):
    id: str
    sala_id: str
    tipo: str                                # equipamento_obrigatorio | especialidade_exclusiva
    valor: str


class Alocacao(BaseModel):
    id: str
    grade_id: str
    sala_id: str
    dia_semana: str
    turno: str


class ResultadoAlocacao(BaseModel):
    """Resultado da tentativa de alocação de uma única grade pelo motor automático
    (src/services/alocacao_engine.py — módulo futuro/experimental, ainda não exposto
    por nenhum endpoint)."""
    grade_id: str
    especialidade: str
    profissional: str
    salas_alocadas: list[str]
    scores: list[int]
    alocado: bool


class ResultadoMotor(BaseModel):
    """Resultado agregado de uma execução do motor de alocação automática."""
    dia_semana: str
    turno: str
    alocacoes: list[ResultadoAlocacao]
    grades_sem_alocacao: list[str]


class Conflito(BaseModel):
    id: str
    tipo: str
    gravidade: str                           # critico | operacional | info
    descricao: str
    grade_id: Optional[str] = None
    sala_id: Optional[str] = None
    alocacao_id: Optional[str] = None
    especialidade: Optional[str] = None
    dia_semana: Optional[str] = None
    turno: Optional[str] = None


class HistoricoAjuste(BaseModel):
    id: str
    alocacao_id: str
    sala_anterior_id: str
    sala_nova_id: str
    data_hora: str
    usuario: str
    justificativa: Optional[str] = None
    conflitos_antes: list[Conflito]
    conflitos_depois: list[Conflito]


class AjusteAlocacaoRequest(BaseModel):
    alocacao_id: str
    nova_sala_id: str
    justificativa: Optional[str] = None


class AjusteAlocacaoResponse(BaseModel):
    alocacao: Alocacao
    conflitos_depois: list[Conflito]
    historico: HistoricoAjuste


class DashboardResumo(BaseModel):
    total_salas: int
    salas_disponiveis: int
    salas_bloqueadas: int
    salas_reforma: int
    total_conflitos: int
    conflitos_criticos: int
    total_grades: int
    total_alocacoes: int
