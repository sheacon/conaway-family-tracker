"""add abbreviation to person

Revision ID: f69d174071c2
Revises: 29949b86062e
Create Date: 2026-03-07 18:12:58.627070

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f69d174071c2'
down_revision = '29949b86062e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('person', schema=None) as batch_op:
        batch_op.add_column(sa.Column('abbreviation', sa.String(length=10), nullable=True))


def downgrade():
    with op.batch_alter_table('person', schema=None) as batch_op:
        batch_op.drop_column('abbreviation')
