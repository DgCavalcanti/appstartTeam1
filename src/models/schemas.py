"""
Schemas Pydantic do SAA — alinhados ao modelo de dados em 04-modelo-dados.md
"""
from pydantic import BaseModel
from typing import Optional


class Grade(BaseModel):
    id: int
    especialidade: str
    profissional: str
    dia_semana: str
    turno: str
    qtd_salas_necessarias: int


class Sala(BaseModel):
    id: int
    numero: str
    andar: str
    bloco: str
    status: str                       # "disponivel" | "bloqueada" | "reforma" | "manutencao"
    tem_equipamento: bool
    acessivel: bool
    especialidade_preferencial: Optional[str] = None
    tem_maca_ginecologica: bool = False


class Restricao(BaseModel):
    id: int
    id_sala: int
    especialidade: str
    tipo_restricao: str
    descricao: str


class Alocacao(BaseModel):
    id: int
    id_grade: int
    id_sala: int
    dia_semana: str
    turno: str
    status: str


class Conflito(BaseModel):
    id: int
    id_grade: int
    id_sala: int
    tipo: str
    gravidade: str                    # "alerta" | "critico"
    descricao: str
    especialidade: str
    dia_semana: str
    turno: str


class ResultadoAlocacao(BaseModel):
    """Resultado do motor de alocação automática para uma grade."""
    id_grade: int
    especialidade: str
    profissional: str
    salas_alocadas: list[int]         # ids das salas escolhidas
    scores: list[int]                 # score correspondente a cada sala
    alocado: bool                     # False quando não há salas suficientes


class ResultadoMotor(BaseModel):
    """Resultado completo de uma rodada do motor de alocação."""
    dia_semana: str
    turno: str
    alocacoes: list[ResultadoAlocacao]
    grades_sem_alocacao: list[int]    # ids das grades que não puderam ser alocadas
