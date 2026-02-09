"""fix unique null tokens"""

from alembic import op
import sqlalchemy as sa

revision = 'add_filtered_unique_indexes_tokens'
down_revision = 'a6176f9fbaac'
branch_labels = None
depends_on = None


def upgrade():
    # 1) Sütunları nullable hale getir
    with op.batch_alter_table('user') as batch:
        batch.alter_column('confirmation_token', existing_type=sa.String(100), nullable=True)
        batch.alter_column('reset_token', existing_type=sa.String(100), nullable=True)

    # 2) Filtreli unique indexler ekle
    op.create_index(
        'uq_user_confirmation_token_not_null',
        'user',
        ['confirmation_token'],
        unique=True,
        mssql_where=sa.text('confirmation_token IS NOT NULL')
    )
    op.create_index(
        'uq_user_reset_token_not_null',
        'user',
        ['reset_token'],
        unique=True,
        mssql_where=sa.text('reset_token IS NOT NULL')
    )


def downgrade():
    # Filtreli indexleri kaldır
    op.drop_index('uq_user_reset_token_not_null', table_name='user')
    op.drop_index('uq_user_confirmation_token_not_null', table_name='user')

    # Eski unique constraintleri geri ekle (istersen)
    with op.batch_alter_table('user') as batch:
        batch.create_unique_constraint('UQ__user__confirmation_token', ['confirmation_token'])
        batch.create_unique_constraint('UQ__user__reset_token', ['reset_token'])
