"""move flight info from trip_person_flight to trip

Revision ID: 29949b86062e
Revises: fef568fe36ae
Create Date: 2026-02-28 17:06:22.326896

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '29949b86062e'
down_revision = 'fef568fe36ae'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add new columns to trip
    with op.batch_alter_table('trip', schema=None) as batch_op:
        batch_op.add_column(sa.Column('outbound_flight', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('return_flight', sa.String(length=100), nullable=True))

    # 2. Data migration: copy first flight entry per trip into the new columns
    conn = op.get_bind()
    if conn.dialect.has_table(conn, 'trip_person_flight'):
        flights = conn.execute(sa.text(
            "SELECT trip_id, outbound_flight, return_flight "
            "FROM trip_person_flight "
            "ORDER BY trip_id, id"
        )).fetchall()
        seen = set()
        for trip_id, outbound, ret in flights:
            if trip_id not in seen:
                seen.add(trip_id)
                conn.execute(sa.text(
                    "UPDATE trip SET outbound_flight = :ob, return_flight = :ret "
                    "WHERE id = :tid"
                ), {"ob": outbound, "ret": ret, "tid": trip_id})

    # 3. Drop old table
    op.drop_table('trip_person_flight')


def downgrade():
    op.create_table('trip_person_flight',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('trip_id', sa.INTEGER(), nullable=False),
        sa.Column('person_id', sa.INTEGER(), nullable=False),
        sa.Column('outbound_flight', sa.VARCHAR(length=100), nullable=True),
        sa.Column('return_flight', sa.VARCHAR(length=100), nullable=True),
        sa.ForeignKeyConstraint(['person_id'], ['person.id'], ),
        sa.ForeignKeyConstraint(['trip_id'], ['trip.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trip_id', 'person_id')
    )

    with op.batch_alter_table('trip', schema=None) as batch_op:
        batch_op.drop_column('return_flight')
        batch_op.drop_column('outbound_flight')
