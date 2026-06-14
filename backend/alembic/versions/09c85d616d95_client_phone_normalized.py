"""client phone_normalized

Revision ID: 09c85d616d95
Revises: 1ea46d45de96
Create Date: 2026-06-14 20:18:51.772347

"""
from alembic import op
import sqlalchemy as sa


revision = '09c85d616d95'
down_revision = '1ea46d45de96'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) добавляем колонку с дефолтом, чтобы существующие строки не падали
    op.add_column(
        'clients',
        sa.Column('phone_normalized', sa.String(length=20), nullable=False, server_default=''),
    )
    # 2) бэкофилл: только цифры, 11-значные с ведущей 7/8 -> 10 цифр
    op.execute(
        r"""
        UPDATE clients SET phone_normalized = CASE
          WHEN length(regexp_replace(phone_primary, '\D', '', 'g')) = 11
               AND substr(regexp_replace(phone_primary, '\D', '', 'g'), 1, 1) IN ('7', '8')
          THEN substr(regexp_replace(phone_primary, '\D', '', 'g'), 2)
          ELSE regexp_replace(phone_primary, '\D', '', 'g')
        END
        """
    )
    op.create_index(
        op.f('ix_clients_phone_normalized'), 'clients', ['phone_normalized'], unique=False
    )
    # дефолт нужен был только для бэкофилла — снимаем (значение проставляет приложение)
    op.alter_column('clients', 'phone_normalized', server_default=None)


def downgrade() -> None:
    op.drop_index(op.f('ix_clients_phone_normalized'), table_name='clients')
    op.drop_column('clients', 'phone_normalized')
