"""Persist customizable overview dashboard sections."""
from alembic import op
import sqlalchemy as sa

revision = "005_dashboard_preferences"
down_revision = "004_browser_pair"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "dashboard_preferences",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("sections", sa.Text(), nullable=False,
                  server_default='["metrics","goal","charts","apps","timeline"]'),
    )

def downgrade():
    op.drop_table("dashboard_preferences")
