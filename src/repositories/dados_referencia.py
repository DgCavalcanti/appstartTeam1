"""
dados_referencia.py — O mapa real do HC e a lista de unidades do ambulatório.

Estes dados vêm de duas planilhas oficiais e foram embutidos aqui para o sistema
ser autossuficiente: quem clona o projeto já tem a estrutura real do prédio e
sabe quais unidades funcionais participam da alocação, sem depender de arquivo
externo. Se o hospital mudar, edita-se esta lista.

Fontes:
  - "HC2.3 Quantitativo de Consultórios 2026 SAA" → PAVIMENTOS
  - "HC3 Grades AGHU - Validação", aba "Validação AGHU" → UNIDADES
    (coluna "Ocupa sala de alocação ambulatorial": SIM/NÃO)
"""

from __future__ import annotations

from src.domain.entidades import capacidade_em_estacoes

# ---------------------------------------------------------------------------
# Estrutura do prédio — 10 pavimentos, 231 estações (9 pavimentos úteis).
# ---------------------------------------------------------------------------
#
# Cada tupla: (bloco, nome, andar, padrão_1est, padrão_2est, esp_1est, esp_2est, fechada)
#
# `andar` é o número do pavimento no prédio (1 = térreo). É por ele que a
# listagem se agrupa — pavimento 1 e todos os seus blocos, depois pavimento 2
# e os seus, e assim por diante — em vez de alfabética por nome de bloco.
#
# O 1º pavimento do Bloco E tem 35 salas fechadas e nenhuma estação aberta; ele
# entra no catálogo por fidelidade, mas com capacidade 0 o motor o ignora — daí
# os "9 pavimentos úteis" que o documento cita.

PAVIMENTOS: tuple[tuple, ...] = (
    ("Bloco D", "3º Pavimento",            3,  9,  0,  0, 0,  0),
    ("Bloco E", "1º Pavimento (Térreo)",   1,  0,  0,  0, 0, 35),
    ("Bloco E", "2º Pavimento",            2, 35,  8, 11, 3,  0),
    ("Bloco E", "3º Pavimento",            3, 27,  0,  0, 0,  0),
    ("Bloco F", "2º Pavimento",            2,  8, 13,  0, 0,  0),
    ("Bloco F", "3º Pavimento",            3, 15,  0,  0, 0,  0),
    ("Bloco F", "4º Pavimento",            4, 26,  0,  0, 0,  0),
    ("Bloco F", "5º Pavimento",            5, 22,  0,  0, 0,  0),
    ("Bloco F", "6º Pavimento",            6,  0,  0, 15, 0,  0),
    ("Bloco Anexo", "1º Pavimento (Térreo)", 1, 11,  2,  0, 0,  0),
)


# ---------------------------------------------------------------------------
# Unidades funcionais — 62 no total, 43 participam do ambulatório.
# ---------------------------------------------------------------------------
#
# `True` = ocupa sala de alocação ambulatorial (entra na alocação).
# `False` = não ocupa sala; é descartada no passo 2 da importação.
#
# Esta lista substitui a antiga heurística do sufixo "(AMBULATÓRIO)", que errava
# em 9 casos: unidades como ENFERMAGEM e FONOAUDIOLOGIA participam sem ter o
# sufixo, enquanto HEMODINÂMICA e MEDICINA NUCLEAR têm o sufixo e não participam.

UNIDADES: tuple[tuple[str, bool], ...] = (
    ("ACUPUNTURA (AMBULATÓRIO)", True),
    ("AGENCIA TRANSFUSIONAL", False),
    ("ALERGIA E IMUNOLOGIA (AMBULATÓRIO)", True),
    ("ANESTESIOLOGIA (AMBULATÓRIO)", True),
    ("ASSISTENCIA FARMACEUTICA", False),
    ("BRONCOSCOPIA", False),
    ("CARDIOLOGIA (AMBULATÓRIO)", True),
    ("CCIH (AMBULATÓRIO)", True),
    ("CIRURGIA BARIATRICA", True),
    ("CIRURGIA BUCOMAXILOFACIAL (AMBULATÓRIO)", True),
    ("CIRURGIA DE CABECA E PESCOCO", True),
    ("CIRURGIA GERAL (AMBULATÓRIO)", True),
    ("CIRURGIA PEDIÁTRICA (AMBULATÓRIO)", True),
    ("CIRURGIA PLÁSTICA (AMBULATÓRIO)", True),
    ("CIRURGIA TORÁCICA (AMBULATÓRIO)", True),
    ("CIRURGIA VASCULAR (AMBULATÓRIO)", True),
    ("CLINICA DA DOR (AMBULATÓRIO)", True),
    ("CLÍNICA MÉDICA (AMBULATÓRIO)", True),
    ("DERMATOLOGIA (AMBULATÓRIO)", True),
    ("EDUCAÇÃO FÍSICA", False),
    ("ENDOCRINOLOGIA (AMBULATÓRIO)", True),
    ("ENDOSCOPIA", False),
    ("ENFERMAGEM", True),
    ("ESPAÇO TRANS (AMBULATÓRIO)", True),
    ("FISIOTERAPIA", False),
    ("FONOAUDIOLOGIA", True),
    ("GASTROENTEROLOGIA (AMBULATÓRIO)", True),
    ("GERIATRIA (AMBULATORIO)", True),
    ("GINECOLOGIA (AMBULATÓRIO)", True),
    ("HEMATOLOGIA (AMBULATÓRIO)", True),
    ("HEMODINAMICA (AMBULATORIO)", False),
    ("HOSPITAL - DIA", False),
    ("INFECTOLOGIA (AMBULATÓRIO)", True),
    ("MEDICINA NUCLEAR (AMBULATORIO)", False),
    ("NEFROLOGIA (AMBULATÓRIO)", True),
    ("NEUROLOGIA (AMBULATÓRIO)", True),
    ("NUCLEO DE ATENCAO A SAUDE DO ESTUDANTE", False),
    ("NUCLEO DE POS-CUIDADOS INTENSIVOS", False),
    ("NUCLEO DE TELESSAUDE", False),
    ("NÚCLEO DO SERVIDOR (AMBULATÓRIO)", False),
    ("NUTRIÇÃO", True),
    ("OBSTETRÍCIA (AMBULATÓRIO)", True),
    ("OFTALMOLOGIA (AMBULATÓRIO)", True),
    ("ONCOLOGIA (AMBULATÓRIO)", True),
    ("ORTOPEDIA (AMBULATÓRIO)", True),
    ("OTORRINOLARINGOLOGIA (AMBULATÓRIO)", True),
    ("PEDIATRIA (AMBULATÓRIO)", True),
    ("PNEUMOLOGIA (AMBULATÓRIO)", True),
    ("PROCTOLOGIA (AMBULATORIO)", True),
    ("PROTECAO DA CRIANCA E ADOLESC CONTRA VIOLENCIA", True),
    ("PSICOLOGIA (AMBULATÓRIO)", True),
    ("PSIQUIATRIA (AMBULATÓRIO)", True),
    ("PUERICULTURA (AMBULATÓRIO)", True),
    ("REUMATOLOGIA (AMBULATÓRIO)", True),
    ("SAUDE OCUPACIONAL E SEGURANCA DO TRABALHO", False),
    ("SERVICO SOCIAL", False),
    ("STT - TESTE", False),
    ("TERAPIA OCUPACIONAL", False),
    ("TRANSPLANTE (AMBULATÓRIO)", True),
    ("UNIDADE DE DIAGNÓSTICO POR IMAGEM", False),
    ("URGENCIA E EMERGENCIA", False),
    ("UROLOGIA (AMBULATÓRIO)", True),
)

#: Versão dos dados de referência. Muda quando esta lista muda — o startup usa
#: para decidir se precisa atualizar um catálogo semeado com dados antigos.
VERSAO = 3


def capacidade_total() -> int:
    """Soma das estações de todos os pavimentos — deve dar 231."""
    return sum(
        capacidade_em_estacoes(
            padrao_1est=p1, padrao_2est=p2, esp_1est=e1, esp_2est=e2
        )
        for _, _, _, p1, p2, e1, e2, _ in PAVIMENTOS
    )


def total_participantes() -> int:
    """Quantas unidades participam do ambulatório — deve dar 43."""
    return sum(1 for _, participa in UNIDADES if participa)
