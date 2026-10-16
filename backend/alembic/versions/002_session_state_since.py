"""Record last session status transition to show accurate break durations."""
from alembic import op
import sqlalchemy as sa
revision="002_state_since"
down_revision="001_initial"
branch_labels=None
depends_on=None
def upgrade():
    op.add_column("work_sessions",sa.Column("state_since",sa.DateTime(timezone=True),nullable=True))
def downgrade():
    op.drop_column("work_sessions","state_since")
