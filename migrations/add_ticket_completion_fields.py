"""Add ticket completion fields

Revision ID: add_ticket_completion_fields
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_ticket_completion_fields'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add new fields to Ticket table
    op.add_column('ticket', sa.Column('completed_at', sa.DateTime(), nullable=True))
    op.add_column('ticket', sa.Column('completed_by', sa.Integer(), nullable=True))
    op.add_column('ticket', sa.Column('assigned_to', sa.Integer(), nullable=True))
    
    # Add new fields to TicketMessage table
    op.add_column('ticket_message', sa.Column('message_type', sa.String(length=20), nullable=True, server_default='text'))
    op.add_column('ticket_message', sa.Column('read_at', sa.DateTime(), nullable=True))
    
    # Add foreign key constraints
    op.create_foreign_key('fk_ticket_completed_by', 'ticket', 'user', ['completed_by'], ['id'])
    op.create_foreign_key('fk_ticket_assigned_to', 'ticket', 'user', ['assigned_to'], ['id'])

def downgrade():
    # Remove foreign key constraints
    op.drop_constraint('fk_ticket_completed_by', 'ticket', type_='foreignkey')
    op.drop_constraint('fk_ticket_assigned_to', 'ticket', type_='foreignkey')
    
    # Remove columns from TicketMessage table
    op.drop_column('ticket_message', 'read_at')
    op.drop_column('ticket_message', 'message_type')
    
    # Remove columns from Ticket table
    op.drop_column('ticket', 'assigned_to')
    op.drop_column('ticket', 'completed_by')
    op.drop_column('ticket', 'completed_at')
