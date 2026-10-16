"""WorkPulse v2 schema, retained historical activity and projects."""
from alembic import op
import sqlalchemy as sa
revision="003_workpulse_v2"
down_revision="002_state_since"
branch_labels=None
depends_on=None

def upgrade():
    tables = {
      "projects": [
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("name",sa.String(120),nullable=False),sa.Column("client",sa.String(120),nullable=False),
        sa.Column("hourly_rate",sa.Float(),nullable=False),sa.Column("budget_hours",sa.Float(),nullable=False),
        sa.Column("archived",sa.Boolean(),nullable=False),sa.UniqueConstraint("user_id","name")],
      "work_tasks": [
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("project_id",sa.Integer(),sa.ForeignKey("projects.id"),nullable=False),sa.Column("name",sa.String(160),nullable=False),
        sa.Column("status",sa.String(24),nullable=False),sa.Column("estimate_minutes",sa.Integer(),nullable=False)],
      "project_rules": [
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("project_id",sa.Integer(),sa.ForeignKey("projects.id"),nullable=False),
        sa.Column("pattern",sa.String(160),nullable=False),sa.UniqueConstraint("user_id","pattern")],
      "active_assignment":[
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),primary_key=True),
        sa.Column("project_id",sa.Integer(),sa.ForeignKey("projects.id"),nullable=True),
        sa.Column("task_id",sa.Integer(),sa.ForeignKey("work_tasks.id"),nullable=True)],
      "privacy_settings":[
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),primary_key=True),
        sa.Column("paused_until",sa.DateTime(timezone=True),nullable=True),
        sa.Column("paused",sa.Boolean(),nullable=False),sa.Column("hide_window_titles",sa.Boolean(),nullable=False),
        sa.Column("retention_days",sa.Integer(),nullable=False),sa.Column("browser_opt_in",sa.Boolean(),nullable=False),
        sa.Column("ai_opt_in",sa.Boolean(),nullable=False),sa.Column("meeting_opt_in",sa.Boolean(),nullable=False)],
      "privacy_rules":[
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("pattern",sa.String(120),nullable=False),sa.Column("action",sa.String(12),nullable=False),
        sa.UniqueConstraint("user_id","pattern")],
      "manual_entries":[
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("project_id",sa.Integer(),sa.ForeignKey("projects.id"),nullable=True),
        sa.Column("task_id",sa.Integer(),sa.ForeignKey("work_tasks.id"),nullable=True),
        sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),sa.Column("ended_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("state",sa.String(24),nullable=False),sa.Column("note",sa.String(300),nullable=False)],
      "idle_reviews":[
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("slice_id",sa.Integer(),sa.ForeignKey("activity_slices.id"),nullable=False,unique=True),
        sa.Column("resolved",sa.Boolean(),nullable=False)],
      "focus_blocks":[
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("task_id",sa.Integer(),sa.ForeignKey("work_tasks.id"),nullable=True),
        sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("finished_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("duration_minutes",sa.Integer(),nullable=False),sa.Column("status",sa.String(12),nullable=False)],
      "calendar_meetings":[
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("external_uid",sa.String(200),nullable=False),sa.Column("title",sa.String(180),nullable=False),
        sa.Column("starts_at",sa.DateTime(timezone=True),nullable=False),sa.Column("ends_at",sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint("user_id","external_uid")]
    }
    for table, columns in tables.items():
        op.create_table(table,*columns)
    with op.batch_alter_table("activity_slices") as batch:
        batch.add_column(sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True))
        batch.add_column(sa.Column("task_id", sa.Integer(), sa.ForeignKey("work_tasks.id"), nullable=True))
    op.create_index("ix_activity_slices_project_id", "activity_slices", ["project_id"])
    for table in ["projects","work_tasks","project_rules","privacy_rules","manual_entries","idle_reviews","focus_blocks","calendar_meetings"]:
        op.create_index("ix_"+table+"_user_id",table,["user_id"])
    op.create_index("ix_work_tasks_project_id","work_tasks",["project_id"])
    op.create_index("ix_manual_entries_started_at","manual_entries",["started_at"])

def downgrade():
    op.drop_index("ix_activity_slices_project_id",table_name="activity_slices")
    # SQLite batch mode is needed to drop FK columns.
    with op.batch_alter_table("activity_slices") as batch:
        batch.drop_column("task_id")
        batch.drop_column("project_id")
    for table in ("calendar_meetings","focus_blocks","idle_reviews","manual_entries","privacy_rules","privacy_settings","active_assignment","project_rules","work_tasks","projects"):
        op.drop_table(table)
