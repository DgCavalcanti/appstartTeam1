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

import csv
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from src.models.schemas import ImportacaoResultado
from src.repositories.implementations.grade_aghu_csv_provider import (
    GradeAghuCsvProvider,
    detect_csv_type,
)
from src.repositories.implementations.consulta_aghu_csv_provider import ConsultaAghuCsvProvider
from src.repositories.implementations.sala_csv_provider import SalaCsvProvider
from src.repositories.implementations.restricao_csv_provider import RestricaoCsvProvider
from src.repositories.implementations.alocacao_saa_csv_provider import AlocacaoSaaCsvProvider
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


async def _salvar_upload(upload: UploadFile, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    _fazer_backup_se_existir(destino)
    with destino.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return destino


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


def _contar_linhas_csv(caminho: Path) -> int:
    """Conta linhas de dados (excluindo cabeçalho) do CSV salvo."""
    with caminho.open("r", encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


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
        from src.repositories.implementations.grade_aghu_csv_provider import _ler_csv_aghu
        linhas, _ = _ler_csv_aghu(temporario)
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

    destino = await _salvar_upload(arquivo, _SALAS_PATH)

    try:
        salas = SalaCsvProvider(caminho=destino).listar_salas()
        linhas_lidas = _contar_linhas_csv(destino)
        return ImportacaoResultado(
            arquivo=arquivo.filename,
            linhas_lidas=linhas_lidas,
            linhas_validas=len(salas),
            registros_unicos=len({s.id for s in salas}),
            avisos=[],
        )
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/restricoes",
    response_model=ImportacaoResultado,
    summary="Importar restricoes.csv",
)
async def importar_restricoes(arquivo: UploadFile):
    if not arquivo.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum arquivo enviado.")

    destino = await _salvar_upload(arquivo, _RESTRICOES_PATH)

    try:
        restricoes = RestricaoCsvProvider(caminho=destino).listar_restricoes()
        linhas_lidas = _contar_linhas_csv(destino)
        return ImportacaoResultado(
            arquivo=arquivo.filename,
            linhas_lidas=linhas_lidas,
            linhas_validas=len(restricoes),
            registros_unicos=len({r.id for r in restricoes}),
            avisos=[],
        )
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "/alocacoes",
    response_model=ImportacaoResultado,
    summary="Importar alocacoes.csv",
)
async def importar_alocacoes(arquivo: UploadFile):
    if not arquivo.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum arquivo enviado.")

    destino = await _salvar_upload(arquivo, _ALOCACOES_PATH)

    try:
        linhas_lidas = _contar_linhas_csv(destino)
        provider = AlocacaoSaaCsvProvider(caminho_alocacoes=destino, caminho_db=_DB_PATH)
        alocacoes = provider._ler_csv_alocacoes()
        avisos: list[str] = []
        if linhas_lidas and not alocacoes:
            avisos.append("Nenhuma alocação válida encontrada no arquivo enviado.")
        elif len(alocacoes) < linhas_lidas:
            avisos.append(
                f"{linhas_lidas - len(alocacoes)} linha(s) inválida(s) foram ignoradas (ver logs do servidor)."
            )
        return ImportacaoResultado(
            arquivo=arquivo.filename,
            linhas_lidas=linhas_lidas,
            linhas_validas=len(alocacoes),
            registros_unicos=len({a.id for a in alocacoes}),
            avisos=avisos,
        )
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


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
