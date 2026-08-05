"""sala especializada por unidade

Revision ID: ec0f53dd5aa5
Revises: 009b219ab88c
Create Date: 2026-08-04 00:00:00.000000

Adiciona `precisa_sala_especializada` a `alocacao_unidade`: a marcação manual
(feita pelo gestor na etapa 2) de que aquela clínica só pode ser alocada numa
sala ESPECIALIZADA (esp_1est/esp_2est), nunca numa PADRÃO. É uma restrição
RÍGIDA — mesmo nível de prioridade que obrigatoriedade de pavimento — e as
salas especializadas passam a ser reservadas para quem tem essa marcação, não
um pool compartilhado.

O default é False: nenhuma clínica existente muda de comportamento com esta
migração — o motor de alocação continua tratando tudo como hoje até o gestor
marcar alguma clínica manualmente.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec0f53dd5aa5'
down_revision: Union[str, Sequence[str], None] = '009b219ab88c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "alocacao_unidade",
        sa.Column(
            "precisa_sala_especializada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # O server_default só existia para as linhas antigas nascerem preenchidas
    # (False, comportamento inalterado); daqui em diante o valor sempre vem
    # do aplicativo — mesmo padrão de `009b219ab88c_andar_do_pavimento.py`.
    with op.batch_alter_table("alocacao_unidade") as lote:
        lote.alter_column("precisa_sala_especializada", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("alocacao_unidade", "precisa_sala_especializada")
