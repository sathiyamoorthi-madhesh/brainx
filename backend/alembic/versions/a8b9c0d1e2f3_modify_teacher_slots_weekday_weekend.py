"""Modify teacher_time_slots for weekday/weekend availability

Revision ID: a8b9c0d1e2f3
Revises: e407347d1daa
Create Date: 2026-02-09 00:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a8b9c0d1e2f3'
down_revision = 'e407347d1daa'
branch_labels = None
depends_on = None


def upgrade():
    # Clear all existing data first (moving to new schema structure)
    op.execute('DELETE FROM teacher_time_slots')
    
    # Drop old columns that are no longer needed
    op.drop_column('teacher_time_slots', 'slot_date')
    op.drop_column('teacher_time_slots', 'slot_start')
    op.drop_column('teacher_time_slots', 'slot_end')
    op.drop_column('teacher_time_slots', 'status')
    op.drop_column('teacher_time_slots', 'booked_by')
    op.drop_column('teacher_time_slots', 'batch_id')
    
    # Add new columns for weekday/weekend availability
    op.add_column('teacher_time_slots', sa.Column('weekday_available', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('teacher_time_slots', sa.Column('weekday_start', sa.Time(), nullable=True))
    op.add_column('teacher_time_slots', sa.Column('weekday_end', sa.Time(), nullable=True))
    op.add_column('teacher_time_slots', sa.Column('weekend_available', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('teacher_time_slots', sa.Column('weekend_start', sa.Time(), nullable=True))
    op.add_column('teacher_time_slots', sa.Column('weekend_end', sa.Time(), nullable=True))
    op.add_column('teacher_time_slots', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    
    # Make teacher_id unique (one availability record per teacher)
    op.create_unique_constraint('uq_teacher_time_slots_teacher_id', 'teacher_time_slots', ['teacher_id'])


def downgrade():
    # Remove unique constraint
    op.drop_constraint('uq_teacher_time_slots_teacher_id', 'teacher_time_slots', type_='unique')
    
    # Remove new columns
    op.drop_column('teacher_time_slots', 'updated_at')
    op.drop_column('teacher_time_slots', 'weekend_end')
    op.drop_column('teacher_time_slots', 'weekend_start')
    op.drop_column('teacher_time_slots', 'weekend_available')
    op.drop_column('teacher_time_slots', 'weekday_end')
    op.drop_column('teacher_time_slots', 'weekday_start')
    op.drop_column('teacher_time_slots', 'weekday_available')
    
    # Restore old columns
    op.add_column('teacher_time_slots', sa.Column('slot_date', sa.Date(), nullable=False))
    op.add_column('teacher_time_slots', sa.Column('slot_start', sa.Time(), nullable=False))
    op.add_column('teacher_time_slots', sa.Column('slot_end', sa.Time(), nullable=False))
    op.add_column('teacher_time_slots', sa.Column('status', sa.Enum('available', 'booked', 'blocked', name='slotstatus'), nullable=False, server_default='available'))
    op.add_column('teacher_time_slots', sa.Column('booked_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('teacher_time_slots', sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=True))
