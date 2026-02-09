"""merge all heads for mssql

Revision ID: a08a444129e3
Revises: 001, 9da40e2f0901, add_filtered_unique_indexes_tokens, add_monthly_payment_table, add_profile_photo_001
Create Date: 2025-08-31 18:17:27.687935

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a08a444129e3'
down_revision = ('001', '9da40e2f0901', 'add_filtered_unique_indexes_tokens', 'add_monthly_payment_table', 'add_profile_photo_001')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
