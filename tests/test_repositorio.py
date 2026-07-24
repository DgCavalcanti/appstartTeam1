"""
test_repositorio.py — Persistência do cenário de alocação.

Cobre a gravação de um cenário autocontido, a clonagem que sustenta o histórico
e os catálogos globais. Fecha com uma checagem de que a migração do Alembic
continua descrevendo o mesmo esquema que os modelos.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.domain.alocacao import EntradaAlocacao, SolverHeuristico
from src.domain.entidades import NUM_TURNOS, Clinica, Pavimento
from src.domain.importacao import GradeDemanda, GradeSlot
from src.domain.processo import PENDENTE, PREENCHIDA, RASCUNHO
from src.models.saa import PavimentoCatalogo, UnidadeCatalogo
from src.repositories import AlocacaoRepository, CatalogoRepository, PavimentoEntrada
from src.resources.database import Base


# ---------------------------------------------------------------------------
# Infraestrutura de teste
# ---------------------------------------------------------------------------


def executar(corotina):
    """
    Roda uma corrotina num banco temporário e limpo.

    Evita a dependência do pytest-asyncio: os testes seguem síncronos e cada um
    recebe seu próprio banco.
    """

    async def _rodar():
        # StaticPool mantém a mesma conexão para todo o teste: sem ele, cada
        # conexão do pool abriria um banco :memory: diferente e as tabelas
        # criadas aqui não seriam vistas pelas consultas seguintes.
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
        )
        try:
            async with engine.begin() as conexao:
                await conexao.run_sync(Base.metadata.create_all)
            fabrica = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with fabrica() as sessao:
                return await corotina(sessao)
        finally:
            # Só depois que a sessão fechou — descartar o engine antes deixaria
            # o rollback do __aexit__ sem conexão.
            await engine.dispose()

    return asyncio.run(_rodar())


async def recarregar(sessao, alocacao_id):
    """
    Simula uma nova requisição: confirma, esquece o cache de identidade e relê.

    Sem o expunge, o cenário recém-criado voltaria do cache com as coleções
    ainda descarregadas — e em contexto assíncrono não existe lazy load.
    """
    await sessao.commit()
    sessao.expunge_all()
    return await AlocacaoRepository(sessao).obter(alocacao_id)


def cenario_de_exemplo():
    """Duas clínicas complementares, dois pavimentos — pequeno e determinístico."""
    manha = tuple(10 if t % 2 == 0 else 0 for t in range(NUM_TURNOS))
    tarde = tuple(0 if t % 2 == 0 else 8 for t in range(NUM_TURNOS))

    clinicas = (
        Clinica(id=1, nome="CARDIOLOGIA", demanda=manha),
        Clinica(id=2, nome="ORTOPEDIA", demanda=tarde),
    )
    slots = (
        GradeSlot("Dr. A", "CARDIOLOGIA", "segunda", "manha"),
        GradeSlot("Dr. B", "CARDIOLOGIA", "segunda", "manha", revisar=True),
        GradeSlot("Dr. B", "ORTOPEDIA", "segunda", "tarde", revisar=True),
    )
    demandas = (
        GradeDemanda("CARDIOLOGIA", "segunda", "manha", 10),
        GradeDemanda("ORTOPEDIA", "segunda", "tarde", 8),
    )
    pavimentos = (
        PavimentoEntrada(bloco="Bloco A", nome="Térreo", padrao_1est=4, padrao_2est=6),
        PavimentoEntrada(bloco="Bloco B", nome="1º andar", padrao_2est=5, esp_1est=2),
    )
    return clinicas, slots, demandas, pavimentos


def resolver(clinicas, pavimentos):
    dominio = tuple(
        Pavimento(id=i, nome=p.nome_completo, capacidade=p.capacidade)
        for i, p in enumerate(pavimentos, start=1)
    )
    return SolverHeuristico().resolver(
        EntradaAlocacao(clinicas=clinicas, pavimentos=dominio)
    )


# ---------------------------------------------------------------------------
# Gravação
# ---------------------------------------------------------------------------


class TestPersistencia:

    def test_grava_cenario_completo(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()
        resultado = resolver(clinicas, pavimentos)

        async def rodar(sessao):
            repo = AlocacaoRepository(sessao)
            cenario = await repo.criar(
                nome="Cenário base",
                clinicas=clinicas,
                slots=slots,
                demandas=demandas,
                pavimentos=pavimentos,
                resultado=resultado,
            )
            return await recarregar(sessao, cenario.id)

        cenario = executar(rodar)

        assert cenario.nome == "Cenário base"
        assert cenario.status == RASCUNHO
        assert cenario.etapa_atual == 1
        assert len(cenario.pavimentos) == 2
        assert len(cenario.unidades) == 2
        assert len(cenario.etapas) == 6

    def test_capacidade_e_derivada_das_contagens(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()

        async def rodar(sessao):
            repo = AlocacaoRepository(sessao)
            cenario = await repo.criar(
                nome="C", clinicas=clinicas, slots=slots,
                demandas=demandas, pavimentos=pavimentos,
            )
            cenario = await recarregar(sessao, cenario.id)
            return {p.nome: (p.capacidade, p.salas_abertas) for p in cenario.pavimentos}

        capacidades = executar(rodar)

        # Térreo: 4×1est + 6×2est = 4 + 12 = 16 estações em 10 salas.
        assert capacidades["Térreo"] == (16, 10)
        # 1º andar: 5×2est + 2×esp1est = 10 + 2 = 12 estações em 7 salas.
        assert capacidades["1º andar"] == (12, 7)

    def test_grava_as_duas_camadas_da_demanda(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()

        async def rodar(sessao):
            repo = AlocacaoRepository(sessao)
            cenario = await repo.criar(
                nome="C", clinicas=clinicas, slots=slots,
                demandas=demandas, pavimentos=pavimentos,
            )
            cenario = await recarregar(sessao, cenario.id)
            return {
                u.unidade_nome: (len(u.slots), len(u.demandas))
                for u in cenario.unidades
            }

        camadas = executar(rodar)
        assert camadas["CARDIOLOGIA"] == (2, 1)
        assert camadas["ORTOPEDIA"] == (1, 1)

    def test_preserva_a_marca_de_revisao(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()

        async def rodar(sessao):
            repo = AlocacaoRepository(sessao)
            cenario = await repo.criar(
                nome="C", clinicas=clinicas, slots=slots,
                demandas=demandas, pavimentos=pavimentos,
            )
            cenario = await recarregar(sessao, cenario.id)
            return sum(1 for u in cenario.unidades for s in u.slots if s.revisar)

        assert executar(rodar) == 2

    def test_grava_o_resultado_e_o_pavimento_de_cada_unidade(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()
        resultado = resolver(clinicas, pavimentos)

        async def rodar(sessao):
            repo = AlocacaoRepository(sessao)
            cenario = await repo.criar(
                nome="C", clinicas=clinicas, slots=slots, demandas=demandas,
                pavimentos=pavimentos, resultado=resultado,
            )
            cenario = await recarregar(sessao, cenario.id)
            return [
                (u.unidade_nome, u.pavimento_alocado_id, len(u.resultados))
                for u in cenario.unidades
            ]

        linhas = executar(rodar)
        for nome, pavimento_id, qtd_resultados in linhas:
            assert pavimento_id is not None, f"{nome} ficou sem pavimento"
            assert qtd_resultados > 0, f"{nome} ficou sem resultado"

    def test_unidades_excluidas_ficam_registradas_como_nao_participantes(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()

        async def rodar(sessao):
            repo = AlocacaoRepository(sessao)
            cenario = await repo.criar(
                nome="C", clinicas=clinicas, slots=slots, demandas=demandas,
                pavimentos=pavimentos, unidades_excluidas=("ALMOXARIFADO",),
            )
            cenario = await recarregar(sessao, cenario.id)
            return {u.unidade_nome: u.participa for u in cenario.unidades}

        participacao = executar(rodar)
        assert participacao["ALMOXARIFADO"] is False
        assert participacao["CARDIOLOGIA"] is True

    def test_etapas_iniciam_com_o_status_certo(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()
        resultado = resolver(clinicas, pavimentos)

        async def rodar(sessao):
            repo = AlocacaoRepository(sessao)
            cenario = await repo.criar(
                nome="C", clinicas=clinicas, slots=slots, demandas=demandas,
                pavimentos=pavimentos, resultado=resultado,
            )
            cenario = await recarregar(sessao, cenario.id)
            return {e.numero: e.status for e in cenario.etapas}

        etapas = executar(rodar)
        assert etapas[1] == PREENCHIDA, "a importação já aconteceu"
        assert etapas[5] == PREENCHIDA, "o motor rodou"
        assert etapas[2] == PENDENTE
        assert etapas[6] == PENDENTE

    def test_lista_do_mais_recente_para_o_mais_antigo(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()

        async def rodar(sessao):
            repo = AlocacaoRepository(sessao)
            for nome in ("primeiro", "segundo", "terceiro"):
                await repo.criar(
                    nome=nome, clinicas=clinicas, slots=slots,
                    demandas=demandas, pavimentos=pavimentos,
                )
            await sessao.commit()
            return [c.nome for c in await repo.listar()], await repo.contar()

        nomes, total = executar(rodar)
        assert total == 3
        assert nomes[0] == "terceiro"


# ---------------------------------------------------------------------------
# Clonagem — a base do histórico de versões
# ---------------------------------------------------------------------------


class TestClonagem:

    def test_clone_copia_os_insumos_e_aponta_a_origem(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()
        resultado = resolver(clinicas, pavimentos)

        async def rodar(sessao):
            repo = AlocacaoRepository(sessao)
            origem = await repo.criar(
                nome="Original", clinicas=clinicas, slots=slots, demandas=demandas,
                pavimentos=pavimentos, resultado=resultado,
            )
            await sessao.commit()

            clone = await repo.clonar(origem.id, "Variação A")
            clone_id, origem_id = clone.id, origem.id
            await sessao.commit()
            sessao.expunge_all()
            return await repo.obter(origem_id), await repo.obter(clone_id)

        origem, clone = executar(rodar)

        assert clone.origem_id == origem.id
        assert clone.nome == "Variação A"
        assert len(clone.pavimentos) == len(origem.pavimentos)
        assert len(clone.unidades) == len(origem.unidades)
        assert len(clone.etapas) == len(origem.etapas)

    def test_clone_e_independente_da_origem(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()

        async def rodar(sessao):
            repo = AlocacaoRepository(sessao)
            origem = await repo.criar(
                nome="Original", clinicas=clinicas, slots=slots,
                demandas=demandas, pavimentos=pavimentos,
            )
            await sessao.commit()
            clone = await recarregar(sessao, (await repo.clonar(origem.id, "Variação")).id)
            origem = await repo.obter(origem.id)

            # Mexer no clone não pode afetar a origem — é o que garante que
            # reabrir um cenário antigo mostre o que gerou aquele resultado.
            clone.pavimentos[0].padrao_1est = 99
            await sessao.commit()

            return origem.pavimentos[0].padrao_1est, clone.pavimentos[0].padrao_1est

        original, alterado = executar(rodar)
        assert original == 4
        assert alterado == 99

    def test_clone_preserva_as_duas_camadas_da_demanda(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()

        async def rodar(sessao):
            repo = AlocacaoRepository(sessao)
            origem = await repo.criar(
                nome="Original", clinicas=clinicas, slots=slots,
                demandas=demandas, pavimentos=pavimentos,
            )
            await sessao.commit()
            clone = await recarregar(sessao, (await repo.clonar(origem.id, "Variação")).id)
            return (
                sum(len(u.slots) for u in clone.unidades),
                sum(len(u.demandas) for u in clone.unidades),
            )

        assert executar(rodar) == (3, 2)

    def test_clonar_cenario_inexistente(self):
        async def rodar(sessao):
            return await AlocacaoRepository(sessao).clonar(999, "X")

        assert executar(rodar) is None

    def test_excluir_leva_junto_o_conteudo_do_cenario(self):
        clinicas, slots, demandas, pavimentos = cenario_de_exemplo()

        async def rodar(sessao):
            from sqlalchemy import func, select
            from src.models.saa import AlocacaoUnidade

            repo = AlocacaoRepository(sessao)
            cenario = await repo.criar(
                nome="Descartável", clinicas=clinicas, slots=slots,
                demandas=demandas, pavimentos=pavimentos,
            )
            await sessao.commit()

            assert await repo.excluir(cenario.id) is True
            await sessao.commit()

            sobraram = await sessao.execute(
                select(func.count()).select_from(AlocacaoUnidade)
            )
            return await repo.contar(), int(sobraram.scalar_one())

        cenarios, unidades_orfas = executar(rodar)
        assert cenarios == 0
        assert unidades_orfas == 0, "as unidades deveriam cair junto com o cenário"


# ---------------------------------------------------------------------------
# Catálogos globais
# ---------------------------------------------------------------------------


class TestCatalogo:

    def test_aprende_unidades_novas_e_ignora_repetidas(self):
        async def rodar(sessao):
            repo = CatalogoRepository(sessao)
            primeira = await repo.aprender_unidades(["CARDIOLOGIA", "ORTOPEDIA"])
            segunda = await repo.aprender_unidades(["Cardiologia", "PEDIATRIA"])
            await sessao.commit()
            return primeira, segunda, len(await repo.listar_unidades())

        primeira, segunda, total = executar(rodar)
        assert primeira == 2
        assert segunda == 1, "'Cardiologia' já era conhecida, só muda a grafia"
        assert total == 3

    def test_unidade_nao_participante_alimenta_o_filtro_do_passo_2(self):
        async def rodar(sessao):
            repo = CatalogoRepository(sessao)
            await repo.aprender_unidades(["CARDIOLOGIA", "ALMOXARIFADO"])
            assert await repo.definir_participacao("Almoxarifado", False) is True
            await sessao.commit()
            return await repo.unidades_excluidas()

        assert executar(rodar) == frozenset({"almoxarifado"})

    def test_definir_participacao_de_unidade_desconhecida(self):
        async def rodar(sessao):
            return await CatalogoRepository(sessao).definir_participacao("XPTO", False)

        assert executar(rodar) is False

    def test_semeia_a_estrutura_do_predio_uma_vez_so(self):
        async def rodar(sessao):
            repo = CatalogoRepository(sessao)
            primeira = await repo.semear_pavimentos()
            segunda = await repo.semear_pavimentos()
            await sessao.commit()
            pavimentos = await repo.listar_pavimentos()
            return primeira, segunda, sum(p.capacidade for p in pavimentos)

        primeira, segunda, capacidade_total = executar(rodar)
        assert primeira == 9
        assert segunda == 0, "semear de novo não pode duplicar"
        assert capacidade_total == 231, "a semente deve reproduzir as 231 estações do HC"


# ---------------------------------------------------------------------------
# O esquema versionado precisa acompanhar os modelos
# ---------------------------------------------------------------------------


class TestEsquemaVersionado:

    def test_a_migracao_cria_as_mesmas_tabelas_dos_modelos(self, tmp_path):
        """
        Guarda contra a armadilha da migração vazia.

        Se alguém criar uma tabela nova sem gerar migração, o Alembic monta um
        banco incompleto e este teste falha — em vez de o problema só aparecer
        quando outra pessoa clonar o projeto.
        """
        import os
        import sqlite3

        from alembic import command
        from alembic.config import Config

        destino = tmp_path / "migrado.db"
        anterior = os.environ.get("SQLITE_DSN")
        os.environ["SQLITE_DSN"] = f"sqlite+aiosqlite:///{destino.as_posix()}"
        try:
            config = Config(str(Path("alembic.ini").resolve()))
            command.upgrade(config, "head")
        finally:
            if anterior is None:
                os.environ.pop("SQLITE_DSN", None)
            else:
                os.environ["SQLITE_DSN"] = anterior

        conexao = sqlite3.connect(destino)
        do_banco = {
            nome
            for (nome,) in conexao.execute(
                "select name from sqlite_master where type='table'"
            )
        } - {"alembic_version"}
        conexao.close()

        dos_modelos = set(Base.metadata.tables)
        assert do_banco == dos_modelos, (
            "migração e modelos divergiram — rode "
            "`alembic revision --autogenerate` num banco limpo"
        )
