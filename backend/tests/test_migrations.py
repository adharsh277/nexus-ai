import os
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_downgrade_cycle(tmp_path):
    test_db_path = tmp_path / "migration_test.db"
    db_url = f"sqlite:///{test_db_path.as_posix()}"

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["url"] = db_url

    # 1. Upgrade to head
    command.upgrade(cfg, "head")
    engine = sa.create_engine(db_url)
    insp = sa.inspect(engine)
    tables = set(insp.get_table_names())
    expected_tables = {
        "users",
        "tasks",
        "conversations",
        "messages",
        "reminders",
        "notifications",
        "documents",
        "document_chunks",
    }
    assert expected_tables.issubset(tables)

    # 2. Reversible downgrade to 0001_initial
    command.downgrade(cfg, "0001_initial")
    insp = sa.inspect(engine)
    tables_after_downgrade = set(insp.get_table_names())
    assert {"reminders", "notifications", "documents", "document_chunks"}.isdisjoint(
        tables_after_downgrade
    )
    assert {"users", "tasks", "conversations", "messages"}.issubset(tables_after_downgrade)

    # 3. Re-upgrade to head
    command.upgrade(cfg, "head")
    insp = sa.inspect(engine)
    tables_reupgrade = set(insp.get_table_names())
    assert expected_tables.issubset(tables_reupgrade)

    engine.dispose()
