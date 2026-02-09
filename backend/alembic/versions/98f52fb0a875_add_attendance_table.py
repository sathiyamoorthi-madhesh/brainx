"""
Add attendance table
Revision ID: 98f52fb0a875
Revises: b9c0d1e2f3a4
Create Date: 2026-02-09 22:13:14.326445

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '98f52fb0a875'
down_revision: Union[str, Sequence[str], None] = 'b9c0d1e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the enum type - use create_type=False since it may already exist
attendancestatus_enum = postgresql.ENUM('present', 'absent', 'late', 'excused', name='attendancestatus', create_type=False)


def upgrade() -> None:
    # Create the enum type if it doesn't exist
    attendancestatus_enum.create(op.get_bind(), checkfirst=True)
    
    op.create_table('attendance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=True),
        sa.Column('student_id', sa.UUID(), nullable=False),
        sa.Column('batch_id', sa.UUID(), nullable=True),
        sa.Column('course_id', sa.UUID(), nullable=True),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('status', attendancestatus_enum, nullable=False),
        sa.Column('remarks', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['batches.id'], ),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
        sa.ForeignKeyConstraint(['session_id'], ['class_sessions.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'student_id', name='uq_attendance_session_student'),
        sa.UniqueConstraint('batch_id', 'date', 'student_id', name='uq_attendance_batch_date_student')
    )
    op.create_index(op.f('ix_attendance_id'), 'attendance', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_attendance_id'), table_name='attendance')
    op.drop_table('attendance')
    # Note: We don't drop the enum here to avoid issues if other things depend on it


