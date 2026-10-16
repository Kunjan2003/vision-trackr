"""Initial local schema with durable work sessions and app classification rules."""
from alembic import op
import sqlalchemy as sa
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("full_name",sa.String(120),nullable=False),
        sa.Column("email",sa.String(254),nullable=False),
        sa.Column("password_hash",sa.String(100),nullable=False),
        sa.Column("department",sa.String(120),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_index("ix_users_email","users",["email"],unique=True)
    op.create_table("work_sessions",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("finished_at",sa.DateTime(timezone=True)),
        sa.Column("last_tick_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("status",sa.String(16),nullable=False))
    op.create_index("ix_work_sessions_user_id","work_sessions",["user_id"])
    op.create_table("activity_slices",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("session_id",sa.Integer(),sa.ForeignKey("work_sessions.id"),nullable=False),
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("ended_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("duration",sa.Float(),nullable=False),
        sa.Column("state",sa.String(24),nullable=False),
        sa.Column("app_name",sa.String(255),nullable=False),
        sa.Column("window_title",sa.String(500),nullable=False),
        sa.Column("category",sa.String(24),nullable=False))
    for name,cols in [("session_id",["session_id"]),("user_id",["user_id"]),("started_at",["started_at"])]:
        op.create_index(f"ix_activity_slices_{name}","activity_slices",cols)
    op.create_table("category_rules",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("pattern",sa.String(120),nullable=False),
        sa.Column("category",sa.String(24),nullable=False),
        sa.Column("enabled",sa.Boolean(),nullable=False),
        sa.UniqueConstraint("user_id","pattern"))
    op.create_index("ix_category_rules_user_id","category_rules",["user_id"])
    op.create_table("user_settings",
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),primary_key=True),
        sa.Column("idle_threshold",sa.Integer(),nullable=False),
        sa.Column("poll_interval",sa.Integer(),nullable=False),
        sa.Column("auto_start",sa.Boolean(),nullable=False),
        sa.Column("break_reminder_minutes",sa.Integer(),nullable=False),
        sa.Column("daily_goal_minutes",sa.Integer(),nullable=False),
        sa.Column("theme",sa.String(10),nullable=False))

def downgrade():
    for table in ("user_settings","category_rules","activity_slices","work_sessions","users"):
        op.drop_table(table)
