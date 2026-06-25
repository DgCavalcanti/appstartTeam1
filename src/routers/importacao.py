"""Router de importação CSV — recebe arquivos e os salva no caminho ativo
lido pelos demais routers (data/vw_grades.csv, data/vw_consultas_2026.csv,
data/salas.csv, data/restricoes.csv, data/alocacoes.csv — ou os caminhos
definidos pelas variáveis de ambiente AGHU_GRADES_PATH, AGHU_CONSULTAS_PATH,
SAA_SALAS_PATH, SAA_RESTRICOES_PATH, SAA_ALOCACOES_PATH).

Um backup do CSV anterior é mantido em data/importados/ antes da
substituição, para permitir recuperação manual se necessário.

POST /api/importacao/aghu/grades
POST /api/importacao/aghu/consultas
POST /api/importacao/salas
POST /api/importacao/restricoes
POST /api/importacao/alocacoes
"""
from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from src.models.schemas import ImportacaoResultado, ResetResultado
from src.providers.implementations.grade_aghu_csv_provider import (
    GradeAghuCsvProvider,
    detect_csv_type,
)
from src.providers.implementations.consulta_aghu_csv_provider import ConsultaAghuCsvProvider
from src.providers.implementations.sala_csv_provider import SalaCsvProvider
from src.providers.implementations.restricao_csv_provider import RestricaoCsvProvider
from src.providers.implementations.alocacao_saa_csv_provider import AlocacaoSaaCsvProvider
from src.routers.aghu import _GRADES_PATH, _CONSULTAS_PATH
from src.routers.sala import _SALAS_PATH
from src.routers.restricao import _RESTRICOES_PATH
from src.routers.alocacao import _ALOCACOES_PATH, _DB_PATH

router = APIRouter(prefix="/api/importacao", tags=["Importação CSV"])

_DIR_BACKUP = Path("data/importados")


def _fazer_backup_se_existir(caminho: Path) -> None:
    if not caminho.exists():
        return
    _DIR_BACKUP.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    destino_backup = _DIR_BACKUP / f"{caminho.stem}.{timestamp}{caminho.suffix}"
    shutil.copyfile(caminho, destino_backup)


async def _salvar_upload_temporario(upload: UploadFile, destino_final: Path) -> Path:
    destino_final.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        delete=False,
        dir=destino_final.parent,
        prefix=f".{destino_final.stem}.upload.",
        suffix=destino_final.suffix,
    ) as f:
        shutil.copyfileobj(upload.file, f)
        return Path(f.name)


def _publicar_upload_validado(origem_temporaria: Path, destino: Path) -> Path:
    _fazer_backup_se_existir(destino)
    origem_temporaria.replace(destino)
    return destino


def _remover_temporario(caminho: Path) -> None:
    try:
        caminho.unlink(missing_ok=True)
    except OSError:
        pass


@router.post(
    "/aghu/grades",
    response_model=ImportacaoResultado,
    summary="Importar vw_grades.csv (formato real AGHU)",
)
async def importar_grades_aghu(arquivo: UploadFile = File(...)):
    if not arquivo.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum arquivo enviado.")

    temporario = await _salvar_upload_temporario(arquivo, _GRADES_PATH)

    try:
        provider = GradeAghuCsvProvider(caminho=temporario)
        # valida tipo do CSV
        from src.providers.implementations.grade_aghu_csv_provider import _ler_csv_aghu
        linhas, _, _ = _ler_csv_aghu(temporario)
        if linhas:
            tipo = detect_csv_type(list(linhas[0].keys()))
            if tipo != "grade_aghu":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Formato não reconhecido como grade AGHU. Tipo detectado: '{tipo}'.",
                )

        r = provider.resumo_importacao()
        _publicar_upload_validado(temporario, _GRADES_PATH)
        return ImportacaoResultado(
            arquivo=arquivo.filename,
            linhas_lidas=r["linhas_lidas"],
            linhas_validas=r["linhas_validas"],
            registros_unicos=r["grades_unicas"],
            avisos=r["avisos"],
        )
    except (FileNotFoundError, ValueError) as e:
        _remover_temporario(temporario)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception:
        _remover_temporario(temporario)
        raise


@router.post(
    "/salas",
    response_model=ImportacaoResultado,
    summary="Importar salas.csv",
)
async def importar_salas(arquivo: UploadFile):
    if not arquivo.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum arquivo enviado.")

    # CORRIGIDO: antes o upload sobrescrevia salas.csv direto e só então
    # validava — um arquivo corrompido (ex.: bytes nulos) já tinha destruído
    # o arquivo ativo antes do erro ser detectado. Agora valida em um arquivo
    # temporário primeiro e só promove para o caminho ativo se passar,
    # igual ao padrão já usado para grades/consultas AGHU.
    temporario = await _salvar_upload_temporario(arquivo, _SALAS_PATH)

    try:
        provider = SalaCsvProvider(caminho=temporario)
        salas = provider.listar_salas()
        # linhas_lidas == len(salas): listar_salas() levanta ValueError se
        # qualquer linha for inválida, então o sucesso implica todas as linhas
        # lidas serem válidas (sem necessidade de reler o arquivo).
        _publicar_upload_validado(temporario, _SALAS_PATH)
        return ImportacaoResultado(
            arquivo=arquivo.filename,
            linhas_lidas=len(salas),
            linhas_validas=len(salas),
            registros_unicos=len({s.id for s in salas}),
            avisos=[provider.ultimo_aviso] if provider.ultimo_aviso else [],
        )
    except (FileNotFoundError, ValueError) as e:
        _remover_temporario(temporario)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception:
        _remover_temporario(temporario)
        raise


@router.post(
    "/restricoes",
    response_model=ImportacaoResultado,
    summary="Importar restricoes.csv",
)
async def importar_restricoes(arquivo: UploadFile):
    if not arquivo.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum arquivo enviado.")

    temporario = await _salvar_upload_temporario(arquivo, _RESTRICOES_PATH)

    try:
        provider = RestricaoCsvProvider(caminho=temporario)
        restricoes = provider.listar_restricoes()
        # linhas_lidas == len(restricoes): listar_restricoes() levanta
        # ValueError se qualquer linha for inválida, então o sucesso implica
        # todas as linhas lidas serem válidas (sem necessidade de reler o
        # arquivo, o que evitamos para não bater de novo no csv.Error de
        # bytes nulos caso a cauda corrompida ainda esteja no arquivo).
        _publicar_upload_validado(temporario, _RESTRICOES_PATH)
        return ImportacaoResultado(
            arquivo=arquivo.filename,
            linhas_lidas=len(restricoes),
            linhas_validas=len(restricoes),
            registros_unicos=len({r.id for r in restricoes}),
            avisos=[provider.ultimo_aviso] if provider.ultimo_aviso else [],
        )
    except (FileNotFoundError, ValueError) as e:
        _remover_temporario(temporario)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception:
        _remover_temporario(temporario)
        raise


@router.post(
    "/alocacoes",
    response_model=ImportacaoResultado,
    summary="Importar alocacoes.csv",
)
async def importar_alocacoes(arquivo: UploadFile):
    if not arquivo.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum arquivo enviado.")

    temporario = await _salvar_upload_temporario(arquivo, _ALOCACOES_PATH)

    try:
        provider = AlocacaoSaaCsvProvider(caminho_alocacoes=temporario, caminho_db=_DB_PATH)
        alocacoes = provider._ler_csv_alocacoes()
        # linhas_lidas vem do provider (já reflete o arquivo pós-truncamento,
        # se houve cauda nula descartada) em vez de reler o arquivo aqui —
        # reler bateria de novo no csv.Error de bytes nulos se a cauda
        # corrompida ainda estiver presente no arquivo em disco.
        linhas_lidas = provider.ultimo_linhas_lidas
        avisos: list[str] = []
        if provider.ultimo_aviso:
            avisos.append(provider.ultimo_aviso)
        if linhas_lidas and not alocacoes:
            avisos.append("Nenhuma alocação válida encontrada no arquivo enviado.")
        elif len(alocacoes) < linhas_lidas:
            avisos.append(
                f"{linhas_lidas - len(alocacoes)} linha(s) inválida(s) foram ignoradas (ver logs do servidor)."
            )
        _publicar_upload_validado(temporario, _ALOCACOES_PATH)
        return ImportacaoResultado(
            arquivo=arquivo.filename,
            linhas_lidas=linhas_lidas,
            linhas_validas=len(alocacoes),
            registros_unicos=len({a.id for a in alocacoes}),
            avisos=avisos,
        )
    except (FileNotFoundError, ValueError) as e:
        _remover_temporario(temporario)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception:
        _remover_temporario(temporario)
        raise


@router.post(
    "/aghu/consultas",
    response_model=ImportacaoResultado,
    summary="Importar vw_consultas_2026.csv (formato real AGHU)",
)
async def importar_consultas_aghu(arquivo: UploadFile = File(...)):
    if not arquivo.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum arquivo enviado.")

    temporario = await _salvar_upload_temporario(arquivo, _CONSULTAS_PATH)

    try:
        provider = ConsultaAghuCsvProvider(caminho=temporario)
        r = provider.resumo_importacao()
        _publicar_upload_validado(temporario, _CONSULTAS_PATH)
        return ImportacaoResultado(
            arquivo=arquivo.filename,
            linhas_lidas=r["linhas_lidas"],
            linhas_validas=r["linhas_validas"],
            registros_unicos=r["registros_unicos"],
            avisos=r["avisos"],
        )
    except (FileNotFoundError, ValueError) as e:
        _remover_temporario(temporario)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception:
        _remover_temporario(temporario)
        raise


# ── Reset de dados ───────────────────────────────────────────────────────────
#
# Zera os dados de um tipo, mantendo um backup automático em data/importados/
# (mesmo diretório/convenção de nome usados pelos backups de importação) e
# preservando o cabeçalho/colunas do arquivo atual, para que o dataset volte
# a um estado "vazio mas funcional" (GET continua retornando [] em vez de
# HTTP 422) até a próxima importação.

_TIPOS_RESET: dict[str, Path] = {
    "grades": _GRADES_PATH,
    "consultas": _CONSULTAS_PATH,
    "salas": _SALAS_PATH,
    "restricoes": _RESTRICOES_PATH,
    "alocacoes": _ALOCACOES_PATH,
}

TipoReset = Literal["grades", "consultas", "salas", "restricoes", "alocacoes"]


def _ler_cabecalho(caminho: Path) -> str | None:
    """Lê só a primeira linha (cabeçalho) de um CSV, preservando as colunas
    exatas do arquivo atual — usado pelo reset para zerar os dados sem perder
    o formato/colunas que a importação original tinha.

    Não faz nenhuma validação de conteúdo (intencional): mesmo um arquivo
    corrompido normalmente tem um cabeçalho legível, e resetar deve funcionar
    mesmo quando o arquivo atual está num estado ruim demais pra ser lido
    pelo provider correspondente.
    """
    if not caminho.exists():
        return None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with caminho.open(encoding=enc) as f:
                primeira = f.readline()
            # corta no primeiro byte nulo, se houver (mesma lógica defensiva
            # usada em _tratar_bytes_nulos nos providers)
            primeira = primeira.split("\x00")[0].rstrip("\r\n")
            return primeira or None
        except UnicodeDecodeError:
            continue
    return None


def _contar_linhas_atuais(tipo: TipoReset, caminho: Path) -> int:
    """Conta quantas linhas de dados existem hoje no arquivo, de forma
    tolerante a erro: se o arquivo atual estiver corrompido/ilegível pelo
    provider, o reset deve funcionar mesmo assim (é justamente um dos
    motivos de se querer resetar) — qualquer erro de leitura aqui só resulta
    em contagem 0, sem impedir o reset de seguir adiante."""
    try:
        if tipo == "grades":
            return len(GradeAghuCsvProvider(caminho=caminho).listar_grades())
        if tipo == "consultas":
            return len(ConsultaAghuCsvProvider(caminho=caminho).listar_linhas_brutas())
        if tipo == "salas":
            return len(SalaCsvProvider(caminho=caminho).listar_salas())
        if tipo == "restricoes":
            return len(RestricaoCsvProvider(caminho=caminho).listar_restricoes())
        if tipo == "alocacoes":
            provider = AlocacaoSaaCsvProvider(caminho_alocacoes=caminho, caminho_db=_DB_PATH)
            return len(provider._ler_csv_alocacoes())
    except Exception:
        return 0
    return 0


@router.post(
    "/reset/{tipo}",
    response_model=ResetResultado,
    summary="Limpar os dados atuais de um tipo (grades, consultas, salas, restricoes ou alocacoes)",
)
async def resetar_dados(tipo: TipoReset):
    destino = _TIPOS_RESET[tipo]

    if not destino.exists():
        return ResetResultado(
            tipo=tipo,
            arquivo=destino.name,
            linhas_removidas=0,
            backup=None,
            mensagem=f"Não havia arquivo '{destino.name}' para limpar — nada foi alterado.",
        )

    linhas_removidas = _contar_linhas_atuais(tipo, destino)
    cabecalho = _ler_cabecalho(destino)

    # _fazer_backup_se_existir() não informa o nome do arquivo que criou,
    # então identificamos o novo backup comparando o conteúdo do diretório
    # antes/depois (mesmo padrão de nome usado pelos backups de importação:
    # "{stem}.{YYYYMMDDHHMMSS}{suffix}").
    backups_antes = set(_DIR_BACKUP.glob(f"{destino.stem}.*{destino.suffix}")) if _DIR_BACKUP.exists() else set()
    _fazer_backup_se_existir(destino)
    backups_depois = set(_DIR_BACKUP.glob(f"{destino.stem}.*{destino.suffix}"))
    novo_backup = next(iter(backups_depois - backups_antes), None)

    if cabecalho:
        # "utf-8" puro (nunca "utf-8-sig") para não injetar um BOM em
        # arquivos que nunca tiveram um — mesmo cuidado da autocura de
        # bytes nulos nos providers (ver nota de BOM nos providers CSV).
        destino.write_text(cabecalho + "\n", encoding="utf-8")
    else:
        # Não foi possível extrair um cabeçalho legível (arquivo já estava
        # vazio ou 100% corrompido antes do reset) — esvazia completamente.
        # A próxima importação vai definir o cabeçalho normalmente.
        destino.write_text("", encoding="utf-8")

    ajustes_removidos = 0
    if tipo == "alocacoes":
        ajustes_removidos = AlocacaoSaaCsvProvider(
            caminho_alocacoes=destino, caminho_db=_DB_PATH
        ).limpar_ajustes()

    partes_mensagem = [
        f"'{destino.name}' foi limpo ({linhas_removidas} linha(s) de dados removida(s))."
    ]
    if novo_backup:
        partes_mensagem.append(f"Backup do conteúdo anterior salvo em '{novo_backup.name}'.")
    if tipo == "alocacoes" and ajustes_removidos:
        partes_mensagem.append(
            f"{ajustes_removidos} ajuste(s) manual(is) de sala também foram removidos do histórico ativo."
        )

    return ResetResultado(
        tipo=tipo,
        arquivo=destino.name,
        linhas_removidas=linhas_removidas,
        backup=str(novo_backup) if novo_backup else None,
        mensagem=" ".join(partes_mensagem),
    )
