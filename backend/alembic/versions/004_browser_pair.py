"""Opt-in browser pairing, no URLs or browsing history stored."""
from alembic import op
import sqlalchemy as sa
revision="004_browser_pair"
down_revision="003_workpulse_v2"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("browser_pair",
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),primary_key=True),
        sa.Column("token_hash",sa.String(64),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
def downgrade():
    op.drop_table("browser_pair")
