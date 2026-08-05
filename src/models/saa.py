"""
saa.py — Modelos ORM do SAA.

O centro do modelo é a `Alocacao`: um cenário completo e autocontido. Tudo que
um cenário usou — unidades, grades, salas, restrições e resultado — pendura
nela. Essa é a base do histórico de versões: importar ou reexecutar não apaga o
que já existe, apenas cria ou atualiza um cenário.

Ao lado ficam os catálogos globais, que sobrevivem entre cenários e
pré-preenchem cada novo.

Referência: SAA_Arquitetura.pdf, seção 5.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.entidades import (
    capacidade_em_estacoes,
    salas_ocupadas,
    total_de_salas,
)
from src.domain.processo import PENDENTE, PRIMEIRA_ETAPA, RASCUNHO
from src.resources.database import Base


def _agora() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# O cenário
# ---------------------------------------------------------------------------


class Alocacao(Base):
    """
    Um cenário de alocação — a raiz do histórico.

    `origem_id` aponta para o cenário do qual este foi clonado, permitindo
    montar variações a partir de uma alocação já feita sem perder a original.
    """

    __tablename__ = "alocacao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RASCUNHO)
    etapa_atual: Mapped[int] = mapped_column(
        Integer, nullable=False, default=PRIMEIRA_ETAPA
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_agora
    )
    origem_id: Mapped[int | None] = mapped_column(
        ForeignKey("alocacao.id", ondelete="SET NULL"), nullable=True
    )

    etapas: Mapped[list["AlocacaoEtapa"]] = relationship(
        back_populates="alocacao",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AlocacaoEtapa.numero",
    )
    unidades: Mapped[list["AlocacaoUnidade"]] = relationship(
        back_populates="alocacao",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AlocacaoUnidade.unidade_nome",
    )
    pavimentos: Mapped[list["Pavimento"]] = relationship(
        back_populates="alocacao",
        cascade="all, delete-orphan",
        lazy="selectin",
        # Pavimento 1 e seus blocos, depois pavimento 2 e os seus, e assim por
        # diante — nunca alfabético por nome de bloco. `id` desempata dentro do
        # mesmo andar, preservando a ordem em que os blocos foram informados.
        order_by="Pavimento.andar, Pavimento.id",
    )
    restricoes: Mapped[list["Restricao"]] = relationship(
        back_populates="alocacao",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class AlocacaoEtapa(Base):
    """
    O status de cada uma das 6 etapas dentro de um cenário.

    O documento descreve os status por etapa na seção 7 sem desenhá-los no
    diagrama; guardá-los numa tabela própria mantém o histórico fiel e deixa a
    regra de invalidação consultável.
    """

    __tablename__ = "alocacao_etapa"
    __table_args__ = (UniqueConstraint("alocacao_id", "numero", name="uq_etapa"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alocacao_id: Mapped[int] = mapped_column(
        ForeignKey("alocacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PENDENTE)
    atualizado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    alocacao: Mapped["Alocacao"] = relationship(back_populates="etapas")


# ---------------------------------------------------------------------------
# Unidades funcionais do cenário
# ---------------------------------------------------------------------------


class AlocacaoUnidade(Base):
    """
    Uma clínica considerada neste cenário.

    `participa` é o que a etapa 2 edita. `pavimento_alocado_id` é preenchido
    pela etapa 5 e vale para a semana inteira — o que varia entre turnos é
    quantas salas a unidade usa, não o pavimento.
    """

    __tablename__ = "alocacao_unidade"
    __table_args__ = (
        UniqueConstraint("alocacao_id", "unidade_nome", name="uq_unidade_no_cenario"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alocacao_id: Mapped[int] = mapped_column(
        ForeignKey("alocacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    unidade_nome: Mapped[str] = mapped_column(String(200), nullable=False)
    participa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Restrição RÍGIDA marcada manualmente pelo gestor (etapa 2): a clínica só
    #: pode ocupar sala ESPECIALIZADA. Mesmo peso de obrigatoriedade de
    #: pavimento — nunca aloca numa sala padrão, pode gerar sobra se não houver
    #: especializada suficiente. Default False preserva o comportamento de
    #: quem nunca marcou nada.
    precisa_sala_especializada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    pavimento_alocado_id: Mapped[int | None] = mapped_column(
        ForeignKey("pavimento.id", ondelete="SET NULL"), nullable=True
    )

    alocacao: Mapped["Alocacao"] = relationship(back_populates="unidades")
    pavimento_alocado: Mapped["Pavimento | None"] = relationship(
        foreign_keys=[pavimento_alocado_id], lazy="selectin"
    )

    slots: Mapped[list["GradeSlot"]] = relationship(
        back_populates="unidade", cascade="all, delete-orphan", lazy="selectin"
    )
    demandas: Mapped[list["GradeDemanda"]] = relationship(
        back_populates="unidade", cascade="all, delete-orphan", lazy="selectin"
    )
    resultados: Mapped[list["AlocacaoResultado"]] = relationship(
        back_populates="unidade", cascade="all, delete-orphan", lazy="selectin"
    )


# ---------------------------------------------------------------------------
# Estrutura física do cenário
# ---------------------------------------------------------------------------


class Pavimento(Base):
    """
    Um pavimento do cenário, com a contagem de salas por tipo.

    A capacidade em estações é derivada — nunca digitada — para não divergir das
    contagens que o gestor edita na etapa 3. Salas fechadas são registradas para
    o gestor ver, mas não entram na capacidade.
    """

    __tablename__ = "pavimento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alocacao_id: Mapped[int] = mapped_column(
        ForeignKey("alocacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bloco: Mapped[str] = mapped_column(String(100), nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Número do andar no prédio (1 = térreo). É por ele que a listagem se
    #: agrupa — nunca por ordem alfabética de bloco.
    andar: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    padrao_1est: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    padrao_2est: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    esp_1est: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    esp_2est: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fechada: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    alocacao: Mapped["Alocacao"] = relationship(back_populates="pavimentos")

    @property
    def capacidade(self) -> int:
        """Capacidade em estações — a moeda do motor de alocação."""
        return capacidade_em_estacoes(
            padrao_1est=self.padrao_1est,
            padrao_2est=self.padrao_2est,
            esp_1est=self.esp_1est,
            esp_2est=self.esp_2est,
        )

    @property
    def capacidade_padrao(self) -> int:
        """
        Estações só das salas PADRÃO (padrao_1est/padrao_2est).

        É o que o motor de alocação usa como capacidade do pool "padrao" deste
        pavimento (ver `src.domain.entidades.capacidade_do_pool`) — as
        estações especializadas ficam de fora de propósito, pois são
        reservadas, não um pool compartilhado.
        """
        return capacidade_em_estacoes(
            padrao_1est=self.padrao_1est,
            padrao_2est=self.padrao_2est,
        )

    @property
    def capacidade_especializada(self) -> int:
        """
        Estações só das salas ESPECIALIZADAS (esp_1est/esp_2est).

        Capacidade do pool "especializada" deste pavimento — reservado às
        clínicas com `precisa_sala_especializada=True`.
        """
        return capacidade_em_estacoes(
            esp_1est=self.esp_1est,
            esp_2est=self.esp_2est,
        )

    @property
    def salas_abertas(self) -> int:
        """Salas físicas em uso — o número que os relatórios mostram."""
        return total_de_salas(
            padrao_1est=self.padrao_1est,
            padrao_2est=self.padrao_2est,
            esp_1est=self.esp_1est,
            esp_2est=self.esp_2est,
        )

    @property
    def nome_completo(self) -> str:
        return f"{self.bloco} — {self.nome}"

    def salas_em_uso(self, estacoes: int) -> int:
        """Quantas salas físicas `estacoes` ocupadas representam (seção 14)."""
        return salas_ocupadas(
            estacoes,
            padrao_1est=self.padrao_1est,
            padrao_2est=self.padrao_2est,
            esp_1est=self.esp_1est,
            esp_2est=self.esp_2est,
        )


class Restricao(Base):
    """
    Liga uma unidade a um pavimento: obrigatoriedade (rígida) ou preferência.

    Só a obrigatoriedade força; a preferência entra como afinidade e cede se o
    pavimento não comportar a clínica inteira.
    """

    __tablename__ = "restricao"
    __table_args__ = (
        UniqueConstraint(
            "alocacao_unidade_id", "pavimento_id", "tipo", name="uq_restricao"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alocacao_id: Mapped[int] = mapped_column(
        ForeignKey("alocacao.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alocacao_unidade_id: Mapped[int] = mapped_column(
        ForeignKey("alocacao_unidade.id", ondelete="CASCADE"), nullable=False
    )
    pavimento_id: Mapped[int] = mapped_column(
        ForeignKey("pavimento.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)

    alocacao: Mapped["Alocacao"] = relationship(back_populates="restricoes")


# ---------------------------------------------------------------------------
# Demanda em duas camadas
# ---------------------------------------------------------------------------


class GradeSlot(Base):
    """
    Camada de origem: uma linha por profissional × dia × turno já tratado.

    É o grão auditável da demanda (~1.400 linhas no arquivo real) e permite
    reprocessar sem reimportar. Não guarda condição de atendimento — descartada
    no tratamento. Guarda `especialidade` apenas como dado auxiliar de
    auditoria: ela nunca decide unidade, pavimento nem demanda agregada — quem
    decide é sempre `Unidade_Funcional`.

    `revisar` marca os casos em que o profissional atende duas clínicas no mesmo
    turno, para a etapa 2 destacar.
    """

    __tablename__ = "grade_slot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alocacao_unidade_id: Mapped[int] = mapped_column(
        ForeignKey("alocacao_unidade.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profissional: Mapped[str] = mapped_column(String(200), nullable=False)
    dia_semana: Mapped[str] = mapped_column(String(20), nullable=False)
    turno: Mapped[str] = mapped_column(String(20), nullable=False)
    revisar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Auxiliar de auditoria — nunca usada para decidir pavimento ou demanda.
    especialidade: Mapped[str | None] = mapped_column(String(400), nullable=True)

    unidade: Mapped["AlocacaoUnidade"] = relationship(back_populates="slots")


class GradeDemanda(Base):
    """
    Camada derivada: a contagem de grades por unidade/dia/turno.

    É o que a etapa 2 exibe e o gestor edita, e o que alimenta o motor.
    """

    __tablename__ = "grade_demanda"
    __table_args__ = (
        UniqueConstraint(
            "alocacao_unidade_id", "dia_semana", "turno", name="uq_demanda"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alocacao_unidade_id: Mapped[int] = mapped_column(
        ForeignKey("alocacao_unidade.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dia_semana: Mapped[str] = mapped_column(String(20), nullable=False)
    turno: Mapped[str] = mapped_column(String(20), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    unidade: Mapped["AlocacaoUnidade"] = relationship(back_populates="demandas")


class AlocacaoResultado(Base):
    """
    O resultado por unidade/dia/turno. Os ajustes manuais da etapa 6 alteram
    diretamente esta tabela, sem refazer o processo desde o início.
    """

    __tablename__ = "alocacao_resultado"
    __table_args__ = (
        UniqueConstraint(
            "alocacao_unidade_id", "dia_semana", "turno", name="uq_resultado"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alocacao_unidade_id: Mapped[int] = mapped_column(
        ForeignKey("alocacao_unidade.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dia_semana: Mapped[str] = mapped_column(String(20), nullable=False)
    turno: Mapped[str] = mapped_column(String(20), nullable=False)
    qtd_alocada: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qtd_nao_alocada: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    unidade: Mapped["AlocacaoUnidade"] = relationship(back_populates="resultados")


# ---------------------------------------------------------------------------
# Catálogos globais — sobrevivem entre cenários
# ---------------------------------------------------------------------------


class UnidadeCatalogo(Base):
    """
    As unidades já conhecidas. Aprende valores novos na importação e
    pré-preenche o próximo cenário.

    `participa_default` é o que responde à pergunta "esta unidade ocupa
    consultório?" — a lista de exclusão do documento vive aqui.
    """

    __tablename__ = "unidade_catalogo"
    __table_args__ = (UniqueConstraint("nome_normalizado", name="uq_unidade_catalogo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Forma sem acento e em caixa baixa — é por ela que a comparação acontece.
    nome_normalizado: Mapped[str] = mapped_column(String(200), nullable=False)
    participa_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )


class PavimentoCatalogo(Base):
    """
    A estrutura do prédio. Pré-preenche os pavimentos de cada novo cenário.

    As contagens de salas são guardadas como ponto de partida; a etapa 3 as
    ajusta dentro do cenário sem afetar o catálogo.
    """

    __tablename__ = "pavimento_catalogo"
    __table_args__ = (UniqueConstraint("bloco", "nome", name="uq_pavimento_catalogo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bloco: Mapped[str] = mapped_column(String(100), nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Número do andar no prédio (1 = térreo). É por ele que a listagem se
    #: agrupa — pavimento 1 e seus blocos, depois pavimento 2 e os seus, etc.
    andar: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    padrao_1est: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    padrao_2est: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    esp_1est: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    esp_2est: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fechada: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    @property
    def capacidade(self) -> int:
        return capacidade_em_estacoes(
            padrao_1est=self.padrao_1est,
            padrao_2est=self.padrao_2est,
            esp_1est=self.esp_1est,
            esp_2est=self.esp_2est,
        )


class RestricaoPadrao(Base):
    """
    Regra padrão de obrigatoriedade/preferência, por Unidade_Funcional e pavimento.

    Vive no catálogo global — sobrevive entre cenários. Ao criar um novo
    cenário, essas regras são copiadas como restrições daquele cenário (pré-
    configuração); dali em diante o gestor edita a cópia livremente, sem afetar
    o padrão global, e editar/remover o padrão não altera cenários já criados.

    `nome_unidade` guarda a grafia original (para exibição); a comparação com
    a grade importada usa sempre a forma normalizada.
    """

    __tablename__ = "restricao_padrao"
    __table_args__ = (
        UniqueConstraint(
            "unidade_normalizada", "pavimento_catalogo_id", name="uq_restricao_padrao"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome_unidade: Mapped[str] = mapped_column(String(200), nullable=False)
    unidade_normalizada: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    pavimento_catalogo_id: Mapped[int] = mapped_column(
        ForeignKey("pavimento_catalogo.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)

    pavimento: Mapped["PavimentoCatalogo"] = relationship(lazy="selectin")
