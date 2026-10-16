from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from workpulse.db import Base
from workpulse import models  # noqa
config = context.config
target_metadata = Base.metadata
def migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
def migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
if context.is_offline_mode():
    migrations_offline()
else:
    migrations_online()
