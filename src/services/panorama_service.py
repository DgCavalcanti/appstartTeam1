"""
panorama_service.py — Etapa 3: o panorama de salas.

O gestor informa quantas salas de cada tipo há em cada pavimento. A capacidade
em estações é sempre derivada — nunca digitada.

Referência: SAA_Arquitetura.pdf, seções 5 e 7.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.saa import Alocacao, Pavimento
from src.services.processo_service import ProcessoService

logger = logging.getLogger(__name__)

ETAPA_PANORAMA = 3

#: As contagens que o gestor edita. `fechada` é registrada mas não entra na
#: capacidade — sala fechada não atende.
CAMPOS_DE_SALA: tuple[str, ...] = (
    "padrao_1est",
    "padrao_2est",
    "esp_1est",
    "esp_2est",
    "fechada",
)


class PanoramaService:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao
        self.processo = ProcessoService(sessao)

    def ler(self, cenario: Alocacao) -> list[dict]:
        """
        A planilha da etapa 3 — já vem na ordem de `cenario.pavimentos`
        (pavimento 1 e seus blocos, depois pavimento 2 e os seus, etc.; nunca
        alfabética por nome de bloco).
        """
        return [
            {
                "id": p.id,
                "bloco": p.bloco,
                "nome": p.nome,
                "andar": p.andar,
                "nome_completo": p.nome_completo,
                **{campo: getattr(p, campo) for campo in CAMPOS_DE_SALA},
                "capacidade": p.capacidade,
                "salas_abertas": p.salas_abertas,
            }
            for p in cenario.pavimentos
        ]

    def capacidade_total(self, cenario: Alocacao) -> int:
        return sum(p.capacidade for p in cenario.pavimentos)

    async def editar(
        self, cenario: Alocacao, pavimento_id: int, contagens: dict[str, int]
    ) -> Pavimento:
        """
        Atualiza as contagens de um pavimento.

        Aceita atualização parcial: campos não informados ficam como estavam.
        """
        pavimento = next(
            (p for p in cenario.pavimentos if p.id == pavimento_id), None
        )
        if pavimento is None:
            raise ValueError(
                f"pavimento {pavimento_id} não pertence ao cenário {cenario.id}"
            )

        desconhecidos = set(contagens) - set(CAMPOS_DE_SALA)
        if desconhecidos:
            raise ValueError(
                f"campos desconhecidos: {sorted(desconhecidos)}. "
                f"Esperado: {list(CAMPOS_DE_SALA)}"
            )

        for campo, valor in contagens.items():
            quantidade = int(valor)
            if quantidade < 0:
                raise ValueError(f"{campo} não pode ser negativo")
            setattr(pavimento, campo, quantidade)

        await self.processo.registrar_alteracao(cenario, ETAPA_PANORAMA)
        logger.info(
            "cenário %d: %s agora tem %d estações",
            cenario.id,
            pavimento.nome_completo,
            pavimento.capacidade,
        )
        return pavimento
