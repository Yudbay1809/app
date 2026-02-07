from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
import os

DATABASE_URL = "sqlite:///./signage.db"  # ganti ke postgres nanti

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


def ensure_sqlite_schema():
    """
    Lightweight runtime schema patching for SQLite.

    `Base.metadata.create_all()` won't add new columns to existing tables.
    This keeps local/dev installs working without requiring Alembic.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        cols = conn.execute(text("PRAGMA table_info(device)")).fetchall()
        col_names = {row[1] for row in cols}  # (cid, name, type, notnull, dflt_value, pk)
        if "orientation" not in col_names:
            conn.execute(text("ALTER TABLE device ADD COLUMN orientation VARCHAR DEFAULT 'portrait'"))
        if "owner_account" not in col_names:
            conn.execute(text("ALTER TABLE device ADD COLUMN owner_account VARCHAR"))

        if "orientation" in col_names or cols:
            conn.execute(text("UPDATE device SET orientation='portrait' WHERE orientation IS NULL OR orientation=''"))

        media_cols = conn.execute(text("PRAGMA table_info(media)")).fetchall()
        media_col_names = {row[1] for row in media_cols}
        if {"id", "name", "path"}.issubset(media_col_names):
            rows = conn.execute(
                text(
                    "SELECT id, name, path FROM media "
                    "WHERE name IS NULL OR trim(name)='' OR lower(trim(name))='unnamed'"
                )
            ).fetchall()
            for media_id, _name, media_path in rows:
                normalized = os.path.basename((media_path or "").replace("\\", "/")).strip()
                if not normalized:
                    normalized = f"media-{media_id}"
                conn.execute(
                    text("UPDATE media SET name=:name WHERE id=:id"),
                    {"name": normalized, "id": media_id},
                )
