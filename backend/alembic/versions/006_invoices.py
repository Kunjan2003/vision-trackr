"""Persist immutable invoice line items separately from changing project rates."""
from alembic import op
import sqlalchemy as sa
revision = "006_invoices"
down_revision = "005_dashboard_preferences"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("invoices", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("number", sa.String(80), nullable=False), sa.Column("client", sa.String(120), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("status", sa.String(12), nullable=False),
        sa.Column("issued_on", sa.String(10), nullable=False), sa.Column("due_on", sa.String(10), nullable=False),
        sa.Column("total", sa.Float(), nullable=False), sa.Column("snapshot", sa.Text(), nullable=False),
        sa.UniqueConstraint("user_id", "number"))

def downgrade():
    op.drop_table("invoices")
