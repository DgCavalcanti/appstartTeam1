"""andar do pavimento

Revision ID: 009b219ab88c
Revises: 5b34eae537c0
Create Date: 2026-07-24 16:23:35.814177

Adiciona o número do andar a `pavimento_catalogo` e `pavimento` — é por ele
que a listagem passa a se agrupar (pavimento 1 e seus blocos, depois
pavimento 2 e os seus, etc.), em vez de alfabética por nome de bloco.

Faz o backfill das linhas já existentes casando (bloco, nome) contra
`dados_referencia.PAVIMENTOS`. Uma linha de `pavimento` (cópia por cenário)
cujo bloco/nome não bate com nenhuma entrada de referência — porque o gestor
customizou o painel de salas daquele cenário — fica com andar 0; é só um
agrupamento de exibição, não afeta capacidade nem o motor de alocação.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009b219ab88c'
down_revision: Union[str, Sequence[str], None] = '5b34eae537c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (bloco, nome) → andar, extraído de dados_referencia.PAVIMENTOS no momento
# desta migração. Copiado em vez de importado: uma migração não deve
# depender do estado futuro do módulo de dados de referência.
_ANDAR_POR_BLOCO_NOME = {
    ("Bloco D", "3º Pavimento"): 3,
    ("Bloco E", "1º Pavimento (Térreo)"): 1,
    ("Bloco E", "2º Pavimento"): 2,
    ("Bloco E", "3º Pavimento"): 3,
    ("Bloco F", "2º Pavimento"): 2,
    ("Bloco F", "3º Pavimento"): 3,
    ("Bloco F", "4º Pavimento"): 4,
    ("Bloco F", "5º Pavimento"): 5,
    ("Bloco F", "6º Pavimento"): 6,
    ("Bloco Anexo", "1º Pavimento (Térreo)"): 1,
}


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "pavimento", sa.Column("andar", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "pavimento_catalogo",
        sa.Column("andar", sa.Integer(), nullable=False, server_default="0"),
    )

    conexao = op.get_bind()
    for tabela in ("pavimento", "pavimento_catalogo"):
        linhas = conexao.execute(
            sa.text(f"SELECT id, bloco, nome FROM {tabela}")
        ).fetchall()
        for id_, bloco, nome in linhas:
            andar = _ANDAR_POR_BLOCO_NOME.get((bloco, nome))
            if andar is None:
                continue
            conexao.execute(
                sa.text(f"UPDATE {tabela} SET andar = :andar WHERE id = :id"),
                {"andar": andar, "id": id_},
            )

    # O server_default só existia para a coluna nascer preenchida nas linhas
    # antigas; daqui em diante o valor sempre vem do aplicativo.
    with op.batch_alter_table("pavimento") as lote:
        lote.alter_column("andar", server_default=None)
    with op.batch_alter_table("pavimento_catalogo") as lote:
        lote.alter_column("andar", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("pavimento_catalogo", "andar")
    op.drop_column("pavimento", "andar")
